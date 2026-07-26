import type { Metadata } from "next"

import { BasicInputFile } from "../../extended-ui/input-file/_components/basic-input-file"
import { InputFileButtonLabel } from "../../extended-ui/input-file/_components/input-file-button-label"
import { InputFileButtonVariants } from "../../extended-ui/input-file/_components/input-file-button-varaints"
import { InputFilePlaceholder } from "../../extended-ui/input-file/_components/input-file-placeholder"
import { BasicInputGroup } from "../../extended-ui/input-group/_components/basic-input-group"
import { InputGroupCheckboxAndRadio } from "../../extended-ui/input-group/_components/input-group-checkbox-and-radio"
import { InputGroupDropdownAndButton } from "../../extended-ui/input-group/_components/input-group-dropdown-button"
import { InputGroupMerged } from "../../extended-ui/input-group/_components/input-group-merged"
import { BasicCheckbox } from "../../ui/checkbox/_components/basic-checkbox"
import { CheckboxDisabled } from "../../ui/checkbox/_components/checkbox-disabled"
import { BasicRadioGroup } from "../../ui/radio-group/_components/basic-radio-group"
import { RadioGroupDisabled } from "../../ui/radio-group/_components/radio-group-disabled"
import { BasicSwitch } from "../../ui/switch/_components/basic-switch"
import { SwitchDisabled } from "../../ui/switch/_components/switch-disabled"
import { BasicInputs } from "./_components/basic-inputs"

// Define metadata for the page
// More info: https://nextjs.org/docs/app/building-your-application/optimizing/metadata
export const metadata: Metadata = {
  title: "Basic Inputs",
}

export default function BasicInputsPage() {
  return (
    <section className="container grid gap-4 p-4 md:grid-cols-2">
      <BasicInputs />
      <div className="grid gap-4">
        <BasicInputFile />
        <InputFilePlaceholder />
        <InputFileButtonLabel />
        <InputFileButtonVariants />
      </div>
      <BasicInputGroup />
      <InputGroupMerged />
      <InputGroupCheckboxAndRadio />
      <InputGroupDropdownAndButton />
      <BasicCheckbox />
      <CheckboxDisabled />
      <BasicRadioGroup />
      <RadioGroupDisabled />
      <BasicSwitch />
      <SwitchDisabled />
    </section>
  )
}
