import Link from "next/link"
import {
  AlertCircle,
  ArrowRight,
  Bug,
  Calendar,
  Check,
  ChevronDown,
  Clock,
  Cloud,
  CreditCard,
  Download,
  Edit,
  File,
  Heart,
  Home,
  Image,
  LinkIcon,
  Mail,
  Map,
  Phone,
  Search,
  Settings,
  Star,
  Trash,
  User,
} from "lucide-react"

import type { IconType } from "../../types"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

const icons: IconType[] = [
  { icon: AlertCircle, name: "AlertCircle" },
  { icon: ArrowRight, name: "ArrowRight" },
  { icon: Check, name: "Check" },
  { icon: ChevronDown, name: "ChevronDown" },
  { icon: Cloud, name: "Cloud" },
  { icon: CreditCard, name: "CreditCard" },
  { icon: Bug, name: "Bug" },
  { icon: Heart, name: "Heart" },
  { icon: Home, name: "Home" },
  { icon: Mail, name: "Mail" },
  { icon: Settings, name: "Settings" },
  { icon: Star, name: "Star" },
  { icon: User, name: "User" },
  { icon: Calendar, name: "Calendar" },
  { icon: Clock, name: "Clock" },
  { icon: Download, name: "Download" },
  { icon: Edit, name: "Edit" },
  { icon: File, name: "File" },
  { icon: Image, name: "Image" },
  { icon: LinkIcon, name: "Link" },
  { icon: Map, name: "Map" },
  { icon: Phone, name: "Phone" },
  { icon: Search, name: "Search" },
  { icon: Trash, name: "Trash" },
]

export function Lucide() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Lucide React Icons</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {icons.map(({ icon: Icon, name }) => (
            <div key={name} className="flex flex-col items-center">
              <Icon className="w-8 h-8 mb-2" />
              <span className="text-sm text-muted-foreground">{name}</span>
            </div>
          ))}
        </div>
      </CardContent>
      <CardFooter className="justify-center">
        <Button asChild>
          <Link
            href="https://lucide.dev/icons/"
            target="_blank"
            rel="noopener noreferrer"
          >
            View all Lucide icons
          </Link>
        </Button>
      </CardFooter>
    </Card>
  )
}
