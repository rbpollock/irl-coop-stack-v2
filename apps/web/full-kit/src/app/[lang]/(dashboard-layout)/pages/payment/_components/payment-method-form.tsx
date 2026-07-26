"use client"

import { useEffect } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"

import type { PaymentMethodFormType, PaymentType } from "../types"

import { PaymentMethodSchema } from "../_schemas/payment-method-schema"

import { getCreditCardBrandName } from "@/lib/utils"

import { ButtonLoading } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { RadioGroup } from "@/components/ui/radio-group"
import { SeparatorWithText } from "@/components/ui/separator"
import { CreditCardBrandIcon } from "@/components/credit-card-brand-icon"
import { SavedCard } from "./saved-card"

interface PaymentMethodFormProps {
  data: PaymentType["savedCards"]
}

export function PaymentMethodForm({
  data: savedCards,
}: PaymentMethodFormProps) {
  const form = useForm<PaymentMethodFormType>({
    resolver: zodResolver(PaymentMethodSchema),
    defaultValues: {
      cardNumber: "",
      cardName: "",
      expiry: "",
      cvc: "",
      saveCard: false,
    },
  })

  const cardNumber = form.watch("cardNumber")
  const cardName = form.watch("cardName")
  const expiry = form.watch("expiry")
  const cvc = form.watch("cvc")
  const { isSubmitting } = form.formState
  const creditCardName = getCreditCardBrandName(cardNumber || "")
  const defaultCard = savedCards.find((card) => card.isDefault)

  useEffect(() => {
    if (defaultCard) {
      form.setValue("savedCardId", defaultCard.id)
    }
  }, [defaultCard, form])

  useEffect(() => {
    if (cardNumber || cardName || expiry || cvc) {
      form.setValue("savedCardId", undefined, { shouldValidate: true })
    }
  }, [cardNumber, cardName, expiry, cvc, form])

  function onSubmit(_data: PaymentMethodFormType) {}

  return (
    <Form {...form}>
      <Card asChild>
        <form
          onSubmit={form.handleSubmit(onSubmit)}
          className="w-full p-6 space-y-6"
        >
          {savedCards && (
            <>
              <FormField
                control={form.control}
                name="savedCardId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Select from the Saved Cards</FormLabel>
                    <FormControl>
                      <RadioGroup value={field.value} className="gap-3 mb-6">
                        {savedCards.map((card) => (
                          <SavedCard
                            key={card.id}
                            card={card}
                            onSelect={field.onChange}
                          />
                        ))}
                      </RadioGroup>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <SeparatorWithText>or</SeparatorWithText>
            </>
          )}

          <FormField
            control={form.control}
            name="cardNumber"
            render={({ field }) => (
              <FormItem className="relative">
                <FormLabel>Card Number</FormLabel>
                <FormControl>
                  <Input
                    type="number"
                    placeholder="1234 5678 9012 3456"
                    className="ps-9"
                    {...field}
                  />
                </FormControl>
                <CreditCardBrandIcon
                  brandName={creditCardName}
                  className="absolute start-3 top-[2rem] h-4 w-4"
                />
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="cardName"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Cardholder&apos;s Name</FormLabel>
                <FormControl>
                  <Input placeholder="John Doe" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="flex gap-x-4">
            <FormField
              control={form.control}
              name="expiry"
              render={({ field }) => (
                <FormItem className="flex-1">
                  <FormLabel>Expiry Date</FormLabel>
                  <FormControl>
                    <Input placeholder="MM/YY" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="cvc"
              render={({ field }) => (
                <FormItem className="flex-1">
                  <FormLabel>CVC</FormLabel>
                  <FormControl>
                    <Input placeholder="123" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          <FormField
            control={form.control}
            name="saveCard"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center gap-x-2">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <FormLabel>Save card for future billing?</FormLabel>
                </div>
                <FormMessage />
              </FormItem>
            )}
          />

          <ButtonLoading isLoading={isSubmitting} size="lg" className="w-full">
            Pay now
          </ButtonLoading>
        </form>
      </Card>
    </Form>
  )
}
