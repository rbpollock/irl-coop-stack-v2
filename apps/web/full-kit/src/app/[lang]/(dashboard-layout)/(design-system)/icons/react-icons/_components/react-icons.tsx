import Link from "next/link"
import {
  FaAmazon,
  FaAndroid,
  FaAngular,
  FaApple,
  FaAws,
  FaBitcoin,
  FaChrome,
  FaDocker,
  FaDropbox,
  FaEthereum,
  FaFacebook,
  FaFirefox,
  FaGithub,
  FaGoogle,
  FaInstagram,
  FaJava,
  FaLinkedin,
  FaMicrosoft,
  FaPython,
  FaReact,
  FaTwitch,
  FaTwitter,
  FaUber,
  FaYoutube,
} from "react-icons/fa"

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
  { icon: FaReact, name: "FaReact" },
  { icon: FaGithub, name: "FaGithub" },
  { icon: FaTwitter, name: "FaTwitter" },
  { icon: FaFacebook, name: "FaFacebook" },
  { icon: FaInstagram, name: "FaInstagram" },
  { icon: FaLinkedin, name: "FaLinkedin" },
  { icon: FaYoutube, name: "FaYoutube" },
  { icon: FaTwitch, name: "FaTwitch" },
  { icon: FaAmazon, name: "FaAmazon" },
  { icon: FaApple, name: "FaApple" },
  { icon: FaGoogle, name: "FaGoogle" },
  { icon: FaMicrosoft, name: "FaMicrosoft" },
  { icon: FaAndroid, name: "FaAndroid" },
  { icon: FaAngular, name: "FaAngular" },
  { icon: FaAws, name: "FaAws" },
  { icon: FaBitcoin, name: "FaBitcoin" },
  { icon: FaChrome, name: "FaChrome" },
  { icon: FaDocker, name: "FaDocker" },
  { icon: FaDropbox, name: "FaDropbox" },
  { icon: FaEthereum, name: "FaEthereum" },
  { icon: FaFirefox, name: "FaFirefox" },
  { icon: FaJava, name: "FaJava" },
  { icon: FaPython, name: "FaPython" },
  { icon: FaUber, name: "FaUber" },
]

export function ReactIcons() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>React Icons</CardTitle>
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
            href="https://react-icons.github.io/react-icons/"
            target="_blank"
            rel="noopener noreferrer"
          >
            View all React Icons
          </Link>
        </Button>
      </CardFooter>
    </Card>
  )
}
