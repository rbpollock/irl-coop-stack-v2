import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { PaymentMethodForm } from "./payment-method-form"

export function PaymentMethod() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Payment Method</CardTitle>
        <CardDescription>
          Choose your payment method and enter your details.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <PaymentMethodForm />
      </CardContent>
    </Card>
  )
}
