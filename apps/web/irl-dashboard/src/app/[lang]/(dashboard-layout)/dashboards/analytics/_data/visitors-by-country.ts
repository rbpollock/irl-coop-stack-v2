import type { VisitorsByCountryDataType } from "../types"

export const visitorsByCountryData: VisitorsByCountryDataType = {
  summary: {
    totalVisitors: 24500,
  },
  countries: [
    {
      countryName: "United States",
      countryCode: "US",
      visitors: 18000,
      percentageChange: 0.1,
    },
    {
      countryName: "Canada",
      countryCode: "CA",
      visitors: 11000,
      percentageChange: 0.08,
    },
    {
      countryName: "United Kingdom",
      countryCode: "GB",
      visitors: 9000,
      percentageChange: -0.01,
    },
    {
      countryName: "India",
      countryCode: "IN",
      visitors: 8500,
      percentageChange: 0.06,
    },
    {
      countryName: "Germany",
      countryCode: "DE",
      visitors: 6400,
      percentageChange: 0.03,
    },
    {
      countryName: "Australia",
      countryCode: "AU",
      visitors: 5500,
      percentageChange: -0.04,
    },
  ],
}
