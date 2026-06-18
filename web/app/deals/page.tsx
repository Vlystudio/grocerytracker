import { redirect } from "next/navigation";

// The deals browser now lives at "/". Keep this path working for old links.
export default function DealsRedirect() {
  redirect("/");
}
