import { userData } from "@/data/user"

import { ProfileContentIntroItem } from "./profile-content-info-intro-item"

export function ProfileContentIntroList() {
  const userInfo = userData
  const location = userInfo.state
    ? userInfo.state + ", " + userInfo.country
    : userInfo.country

  return (
    <ul className="grid gap-y-3">
      <ProfileContentIntroItem
        title="Works as a"
        value={
          <>
            {userInfo.role} <span className="text-foreground"> at </span>{" "}
            {userInfo.organization}
          </>
        }
        iconName="BriefcaseBusiness"
      />
      <ProfileContentIntroItem
        title="Lives in"
        value={location}
        iconName="House"
      />

      <ProfileContentIntroItem
        title="Email"
        value={userInfo.email}
        iconName="Mail"
      />

      <ProfileContentIntroItem
        title="Phone Number"
        value={userInfo.phoneNumber}
        iconName="Phone"
      />
      <ProfileContentIntroItem
        title="Language"
        value={userInfo.language}
        iconName="Languages"
      />
    </ul>
  )
}
