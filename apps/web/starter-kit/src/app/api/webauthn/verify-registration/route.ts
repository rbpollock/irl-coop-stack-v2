import { NextResponse } from 'next/server';
import { verifyRegistrationResponse } from '@simplewebauthn/server';
import * as jwt from 'jsonwebtoken';

const rpID = 'localhost';
const origin = `http://${rpID}:3000`;

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const expectedChallenge = body.expectedChallenge; 

    const verification = await verifyRegistrationResponse({
      response: body,
      expectedChallenge,
      expectedOrigin: origin,
      expectedRPID: rpID,
      requireUserVerification: true,
    });

    if (verification.verified) {
      const credentialPublicKey = verification.registrationInfo?.credentialPublicKey;
      
      const mockKeycloakToken = jwt.sign(
        { sub: "mock-user-id-123", email: "testuser@irl.coop" }, 
        "local-development-secret-irl-coop-v4", 
        { expiresIn: "1h" }
      );

      return NextResponse.json({ 
        verified: true, 
        mockJwt: mockKeycloakToken,
        pubKeyBytes: credentialPublicKey ? Buffer.from(credentialPublicKey).toString('hex') : null
      });
    } else {
      return NextResponse.json({ error: 'Verification failed' }, { status: 400 });
    }
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 400 });
  }
}
