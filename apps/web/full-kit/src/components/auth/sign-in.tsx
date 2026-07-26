import type { DictionaryType } from "@/lib/get-dictionary"

import {
  Auth,
  AuthDescription,
  AuthForm,
  AuthHeader,
  AuthTitle,
} from "./auth-layout"
import { SignInForm } from "./sign-in-form"

export function SignIn({ dictionary }: { dictionary: DictionaryType }) {
  return (
    <Auth
      imgSrc="/images/illustrations/misc/welcome.svg"
      dictionary={dictionary}
    >
      <AuthHeader>
        <AuthTitle>Sign In</AuthTitle>
        <AuthDescription>
          Enter your email below to sign in to your account
        </AuthDescription>
      </AuthHeader>
      <AuthForm>
        <SignInForm />
      </AuthForm>
    </Auth>
  )
}
