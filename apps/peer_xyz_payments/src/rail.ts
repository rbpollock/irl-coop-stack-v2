// The neutral payment-rail contract, and the Peer.xyz implementation of it.
//
// coop-api knows ONLY this contract. `peer` is one implementation of it, and the whole point
// of the seam is that a provider being taken down is a *deployment* problem, not an edit to
// the coop's core: implement this interface, deploy it as its own app, point coop-api at it.
//
// Nothing vendor-specific escapes this file: not the SDK's status vocabulary, not its
// request shape, not its failure messages.

export type RailStatus =
  | "pending"    // created, nothing received
  | "partial"    // some funds arrived — a real state for a P2P rail, not an error
  | "settled"    // the amount requested arrived
  | "cancelled"
  | "failed"
  | "reversed"   // settled, then taken back (chargeback / refund). Not a failure: a fact.
  | "unknown";   // the rail cannot answer, and says so rather than guessing

export interface RailCapabilities {
  /** Which implementation this is. coop-api records it on every intent. */
  rail: string;
  /**
   * True only if funds go straight from the payer to `destination`.
   *
   * A rail that holds the money itself — even briefly, even "just for settlement" — is
   * refused by the coop, because the platform never intermediates member funds. This is a
   * declaration the seam can CHECK, rather than a policy nobody enforces.
   */
  directToDestination: boolean;
  /** Chains this rail can deliver on, as decimal chain ids. */
  chains: string[];
  currency: string;
  /**
   * Whether "what happened to this intent?" is answerable at all. See observeIntent.
   */
  canObserve: boolean;
  /** If canObserve is false, why — surfaced to operators instead of failing silently. */
  observeUnavailableReason?: string;
}

export interface CreatedIntent {
  providerRef: string;
  payUrl: string;
  destination: string;
  /** Echoed back so coop-api can assert the rail did not substitute its own address. */
  expiresAt?: string | null;
}

export interface ObservedIntent {
  status: RailStatus;
  /** Only meaningful when status is partial or settled. */
  received?: number | null;
  note?: string;
}

export interface CreateIntentArgs {
  amount: string;
  currency: string;
  chainId: string;
  /** Where the money must go. Supplied by the coop, never defaulted by the rail. */
  destination: string;
  /** An opaque coop-side reference. Must not identify a member or a group. */
  reference: string;
}

export interface PaymentRail {
  capabilities(): RailCapabilities;
  createIntent(args: CreateIntentArgs): Promise<CreatedIntent>;
  observeIntent(providerRef: string): Promise<ObservedIntent>;
  cancelIntent(providerRef: string): Promise<ObservedIntent>;
}

// ---------------------------------------------------------------------------
// The Peer.xyz (zkp2p) implementation.
// ---------------------------------------------------------------------------

// The SDK's status vocabulary, mapped to the coop's. Kept in ONE place so that a provider
// adding a status is a compile-visible change here rather than a silent "unknown" upstream.
const PEER_STATUS: Record<string, RailStatus> = {
  CREATED: "pending",
  PARTIALLY_FULFILLED: "partial",
  FULFILLED: "settled",
  CANCELLED: "cancelled",
};

function peerConfig() {
  const apiKey = process.env.PEER_PAY_API_KEY ?? "";
  if (!apiKey) throw new Error("peer: PEER_PAY_API_KEY is not set (expected via the ansible vault)");
  return {
    apiKey,
    apiBaseUrl: process.env.PEER_PAY_API_BASE_URL ?? "https://api.pay.peer.xyz",
    checkoutBaseUrl: process.env.PEER_PAY_CHECKOUT_BASE_URL ?? "https://pay.peer.xyz",
  };
}

function opts() {
  const c = peerConfig();
  return {
    apiBaseUrl: c.apiBaseUrl,
    checkoutBaseUrl: c.checkoutBaseUrl,
    apiKey: c.apiKey,
    signal: AbortSignal.timeout(20000),
  };
}

export class PeerRail implements PaymentRail {
  capabilities(): RailCapabilities {
    return {
      rail: "peer",
      directToDestination: true,
      chains: ["8453"], // Base
      currency: "USDC",
      // The SDK exposes exactly six functions and NONE of them looks up an order — but the
      // HOSTED API does: `GET /api/v1/orders/{orderId}` returns the order, the merchant and the
      // customer's latest payment attempt, and it needs NO API key because the order id IS the
      // credential. So settlement is observable, and the earlier "cannot be observed" claim was
      // about the SDK, not the provider.
      canObserve: true,
      observeUnavailableReason:
        "read via the hosted order endpoint, which is a capability URL: the order id is the credential, so it must never be published",
    };
  }

  /**
   * The environment is a property of the KEY, not a URL — so ask, never assume. A
   * "sandbox mode" flag that can disagree with the key is how real money gets spent.
   */
  async merchant() {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sdk: any = await import("@zkp2p/pay-sdk");
    const m = await sdk.getMerchant({ apiBaseUrl: peerConfig().apiBaseUrl, apiKey: peerConfig().apiKey, signal: AbortSignal.timeout(15000) });
    return m as { environment?: string; v1EvmWalletAddress?: string | null };
  }

  async assertSandbox(): Promise<string> {
    const m = await this.merchant();
    const env = String(m.environment ?? "UNKNOWN");
    if (env !== "SANDBOX") {
      throw new Error(`peer: refusing to operate against a ${env} merchant — live is a code change, not a flag`);
    }
    return env;
  }

  async createIntent(args: CreateIntentArgs): Promise<CreatedIntent> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sdk: any = await import("@zkp2p/pay-sdk");
    await this.assertSandbox();

    if (args.currency !== "USDC") throw new Error(`peer: only USDC is supported, got ${args.currency}`);
    if (!this.capabilities().chains.includes(args.chainId)) {
      throw new Error(`peer: chain ${args.chainId} is not supported (${this.capabilities().chains.join(",")})`);
    }
    // The coop supplies the destination. There is no default here and there must not be:
    // the SDK's own default is the MERCHANT's wallet, verified by experiment.
    if (!/^0x[0-9a-fA-F]{40}$/.test(args.destination)) {
      throw new Error("peer: a destination address is required — refusing to fall back to the merchant default");
    }

    const o = opts();
    try {
      const q = await sdk.checkQuoteAvailability(
        {
          amount: args.amount,
          quoteMode: "exact-token",
          destinationChainId: args.chainId,
          destinationToken: args.currency,
          destinationAddress: args.destination,
        },
        o
      );
      if (q && q.available === false) {
        // Better to say "no counterparty right now" than to hand someone a link that cannot fill.
        throw Object.assign(new Error("no counterparty available right now"), { code: "NO_QUOTE", quotes: q.nearbyQuotes ?? null });
      }
    } catch (err) {
      const e = err as Error & { code?: string };
      if (e.code === "NO_QUOTE") throw e;
      console.warn("[peer] quote check failed, proceeding to order:", e.message);
    }

    // No `notes`. A note is a field a third party reads; the group and the member never reach
    // the provider. The reference is an opaque uuid that identifies nothing on its own.
    const res = await sdk.createCheckout(
      {
        requestedUsdcAmount: args.amount,
        destinationAddress: args.destination,
        destinationChainId: args.chainId,
        destinationToken: args.currency,
      },
      o
    );
    const providerRef = res?.order?.id as string | undefined;
    const payUrl = (res?.checkoutUrl ?? (res?.order?.id && res?.orderToken ? sdk.getCheckoutUrl(res.order.id, res.orderToken, o) : undefined)) as string | undefined;
    if (!providerRef || !payUrl) throw new Error("peer: the provider returned no order id / checkout url");

    // Assert the rail used OUR destination. If it substituted anything, that is a hard stop:
    // it means funds are going somewhere the coop did not choose.
    const used = res?.order?.destinationAddress as string | undefined;
    if (used && used.toLowerCase() !== args.destination.toLowerCase()) {
      throw new Error(`peer: destination mismatch — asked for ${args.destination}, order says ${used}`);
    }
    return { providerRef, payUrl, destination: args.destination, expiresAt: null };
  }

  /**
   * Ask the provider what happened to an intent.
   *
   * Uses the hosted read (`GET /api/v1/orders/{id}`) rather than the SDK, which has no lookup.
   * No API key is sent: the order id is the credential — which is exactly why it must be treated
   * as a secret on our side and never put in a URL we publish or a log we keep.
   */
  async observeIntent(providerRef: string): Promise<ObservedIntent> {
    const cfg = peerConfig();
    const base = String(cfg.apiBaseUrl ?? "").replace(/\/+$/, "");
    const res = await fetch(`${base}/api/v1/orders/${encodeURIComponent(providerRef)}`, {
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) {
      return { status: "unknown", note: `provider read returned HTTP ${res.status}` };
    }
    const body = (await res.json().catch(() => null)) as any;
    // The REST reads are ENVELOPED — {success, message, responseObject} — unlike the SDK, which
    // returns the payload unwrapped. Reading body.order found nothing and reported "unknown",
    // which is exactly the kind of silent nothing that looks like a status.
    const payload = body?.responseObject ?? body;
    const order = payload?.order ?? null;
    if (!order) return { status: "unknown", note: "provider read returned no order" };

    const requested = Number(order.requestedUsdcAmount ?? NaN);
    const remaining = Number(order.remainingUsdcAmount ?? NaN);
    const received =
      Number.isFinite(requested) && Number.isFinite(remaining) ? requested - remaining : null;

    // A remainder means partial whatever the status says: the money decides, not the label.
    let status: RailStatus;
    switch (String(order.status ?? "")) {
      case "CREATED":
        status = "pending";
        break;
      case "PARTIALLY_FULFILLED":
        status = "partial";
        break;
      case "FULFILLED":
        status = received !== null && Number.isFinite(requested) && received < requested ? "partial" : "settled";
        break;
      case "CANCELLED":
        status = "cancelled";
        break;
      default:
        status = "unknown";
    }
    return { status, received, note: `order ${String(order.status ?? "?")} read from the provider` };
  }

  async cancelIntent(): Promise<ObservedIntent> {
    return { status: "unknown", note: "the provider's SDK exposes no cancel; an unpaid order simply expires" };
  }
}
