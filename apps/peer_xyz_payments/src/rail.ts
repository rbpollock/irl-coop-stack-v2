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
      // The SDK exposes exactly six functions and NONE of them looks up an order:
      // checkQuoteAvailability, createCheckout, createCheckoutAndRedirect, getCheckoutUrl,
      // getMerchant, redirectToCheckout. So settlement cannot be polled, and the cooperative
      // truth is "we cannot answer" rather than a status invented from hope.
      canObserve: false,
      observeUnavailableReason:
        "the provider's SDK exposes no order lookup; settlement must arrive by webhook or operator confirmation",
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

  async observeIntent(): Promise<ObservedIntent> {
    // Honest: the provider cannot be asked. Returning "pending" here would be a fabricated
    // status — a settled payment would sit looking unpaid forever, and worse, the reverse
    // would credit money that never arrived.
    return { status: "unknown", note: this.capabilities().observeUnavailableReason };
  }

  async cancelIntent(): Promise<ObservedIntent> {
    return { status: "unknown", note: "the provider's SDK exposes no cancel; an unpaid order simply expires" };
  }
}
