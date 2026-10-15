import { redirect } from "next/navigation";

// Question editing moved onto each security's page under /model.
export default function ThesesPage() {
  redirect("/model");
}
