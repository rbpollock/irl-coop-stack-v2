import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
} from "@/components/ui/navigation-menu"

export function BasicNavigationMenu() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Basic Navigation Menu</CardTitle>
      </CardHeader>
      <CardContent className="flex justify-center items-center">
        <NavigationMenu>
          <NavigationMenuList>
            <NavigationMenuItem>
              <NavigationMenuTrigger>Item One</NavigationMenuTrigger>
              <NavigationMenuContent>
                <ul className="w-40 grid gap-2 p-3">
                  <li>
                    <NavigationMenuLink>Link 1</NavigationMenuLink>
                  </li>
                  <li>
                    <NavigationMenuLink>Link 2</NavigationMenuLink>
                  </li>
                </ul>
              </NavigationMenuContent>
            </NavigationMenuItem>
          </NavigationMenuList>
        </NavigationMenu>
      </CardContent>
    </Card>
  )
}
