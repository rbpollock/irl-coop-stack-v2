import { NextResponse } from 'next/server';
import { generateRegistrationOptions } from '@simplewebauthn/server';

const rpName = 'irl.coop Sovereign Node';
const rpID = 'localhost';

export async function GET() {
  const options = await generateRegistrationOptions({
    rpName,
    rpID,
    userID: "mock-user-id-123" as any, // Cast to any to bypass strict type check for now
    userName: "testuser@irl.coop",
    authenticatorSelection: {
      residentKey: 'required',
      userVerification: 'required',
    },
  });

  return NextResponse.json(options);
}
