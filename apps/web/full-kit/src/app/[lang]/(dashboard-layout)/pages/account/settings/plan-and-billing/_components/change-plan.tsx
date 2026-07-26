import { plansData } from "../../../_data/plans"
import { subscriptionsData } from "../../../_data/subscriptions"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ChangePlanForm } from "./change-plan-form"

export function ChangePlan() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Change Plan</CardTitle>
        <CardDescription>
          Choose the plan that best fits your needs. Prices shown are per month.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ChangePlanForm plans={plansData} subscriptions={subscriptionsData} />
      </CardContent>
    </Card>
  )
}
