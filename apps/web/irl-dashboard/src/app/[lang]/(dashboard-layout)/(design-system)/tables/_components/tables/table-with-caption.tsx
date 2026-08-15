import { invoicesData } from "../../_data/invoices"

import { isEven } from "@/lib/utils"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export default function TableWithCaption() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Table with Caption</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableCaption className="mb-4">
            A list of your recent invoices.
          </TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px]">Invoice</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Method</TableHead>
              <TableHead className="text-right">Amount</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {invoicesData.map((invoice, index) => (
              <TableRow
                key={invoice.id}
                className={isEven(index) ? "bg-muted/50" : ""}
              >
                <TableCell className="font-medium">{invoice.id}</TableCell>
                <TableCell>{invoice.status}</TableCell>
                <TableCell>{invoice.method}</TableCell>
                <TableCell className="text-right">{invoice.amount}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
