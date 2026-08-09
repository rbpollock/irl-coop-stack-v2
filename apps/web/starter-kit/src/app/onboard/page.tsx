'use client';

import { useState } from 'react';
import { signIn, useSession } from 'next-auth/react';
import { startRegistration } from '@simplewebauthn/browser';
import { useRouter } from 'next/navigation';

export default function Onboard() {
  const { data: session, status } = useSession();
  const [logs, setLogs] = useState<string[]>([]);
  const [safeAddress, setSafeAddress] = useState<string | null>(null);
  const router = useRouter();

  const addLog = (msg: string) => setLogs(prev => [...prev, msg]);

  const handleWebAuthnRegistration = async () => {
    try {
      addLog('Fetching registration options from /api/webauthn/generate-registration-options...');
      const resp = await fetch('/api/webauthn/generate-registration-options');
      const options = await resp.json();

      addLog('Prompting browser for biometric Passkey creation...');
      const attResp = await startRegistration(options);
      
      // We pass the challenge back to the verify route (in production this comes from a session store)
      (attResp as any).expectedChallenge = options.challenge;

      addLog('Sending biometric response to /api/webauthn/verify-registration...');
      const verificationResp = await fetch('/api/webauthn/verify-registration', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(attResp),
      });

      const verificationJSON = await verificationResp.json();
      
      if (verificationJSON.verified) {
        addLog('Passkey Verified! Requesting Safe deployment from coop-api...');
        
        // Trigger the coop-api deployment using the mock Keycloak JWT returned from verify-registration
        const deployResp = await fetch('http://localhost:3001/api/onboard', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${verificationJSON.mockJwt}`
          },
          body: JSON.stringify({
            pubKeyBytes: verificationJSON.pubKeyBytes
          })
        });

        const deployJSON = await deployResp.json();
        
        if (deployJSON.success) {
          addLog(`✅ Safe Deployed Successfully: ${deployJSON.safeAddress}`);
          setSafeAddress(deployJSON.safeAddress);
          
          addLog('Redirecting to dashboard in 2 seconds...');
          setTimeout(() => {
            router.push('/dashboard');
          }, 2000);
        } else {
          addLog(`❌ Deployment failed: ${JSON.stringify(deployJSON)}`);
        }
      } else {
        addLog('❌ Passkey Verification failed on the server.');
      }
    } catch (error: any) {
      addLog(`❌ Error: ${error.message}`);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-8 text-white bg-slate-950">
      <div className="w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-xl">
        <h1 className="text-3xl font-bold mb-6 text-cyan-400">irl.coop Sovereign Onboarding</h1>
        
        {status === 'loading' ? (
          <p className="text-slate-400">Loading session...</p>
        ) : status === 'unauthenticated' ? (
          <div className="space-y-4">
            <p className="text-slate-300">
              Welcome to the Sovereign OS. Your first step is to authenticate with our federated Keycloak provider.
            </p>
            <button 
              onClick={() => signIn('keycloak')}
              className="px-6 py-3 bg-emerald-600 hover:bg-emerald-500 rounded-md font-semibold text-white transition-colors"
            >
              Sign In with Keycloak
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
              <p className="text-sm text-slate-400 uppercase font-semibold">Authenticated As</p>
              <p className="text-lg text-white font-mono">{session?.user?.email}</p>
            </div>

            <p className="text-slate-300">
              Your identity is verified. The next step is to generate a local cryptographic Passkey (WebAuthn) 
              to serve as the root key for your ERC-4337 Safe.
            </p>

            <button 
              onClick={handleWebAuthnRegistration}
              className="px-6 py-3 bg-cyan-600 hover:bg-cyan-500 rounded-md font-semibold text-white transition-colors"
            >
              Create Passkey & Deploy Safe
            </button>

            {logs.length > 0 && (
              <div className="mt-8 p-4 bg-black rounded-lg font-mono text-sm border border-slate-800 overflow-x-auto">
                <h3 className="text-slate-500 mb-2">// Onboarding Execution Logs</h3>
                {logs.map((log, i) => (
                  <div key={i} className="text-slate-300 py-1">{log}</div>
                ))}
              </div>
            )}

            {safeAddress && (
              <div className="mt-6 p-6 bg-emerald-900/30 border border-emerald-500/50 rounded-lg text-center animate-in fade-in zoom-in">
                <p className="text-emerald-400 font-semibold mb-2">Stage 1 Sovereign Safe Ready</p>
                <p className="text-xl font-mono text-white">{safeAddress}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}