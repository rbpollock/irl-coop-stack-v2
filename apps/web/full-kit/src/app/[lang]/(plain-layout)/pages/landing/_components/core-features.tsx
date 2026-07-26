import { CoreFeaturesList } from "./core-features-list"

export function CoreFeatures() {
  return (
    <section id="features" className="container grid gap-8">
      <div className="text-center mx-auto space-y-1.5">
        <h2 className="text-4xl font-semibold">Core Features</h2>
        <p className="max-w-prose text-sm text-muted-foreground">
          Shadboard provides all the essentials to create scalable,
          user-friendly applications, ensuring a smooth development process.
        </p>
      </div>
      <CoreFeaturesList />
    </section>
  )
}
