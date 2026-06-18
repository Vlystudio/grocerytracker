"use server";

// Server Actions for admin mutations. These run on the server with the logged-in
// user's session, so Supabase RLS enforces that only authenticated admins can
// write. The service-role key is never involved here.
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

function parseList(value: FormDataEntryValue | null): string[] {
  return String(value ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

async function requireUser() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");
  return supabase;
}

// ---- Sources ----------------------------------------------------------

export async function saveSource(formData: FormData) {
  const supabase = await requireUser();

  const id = formData.get("id") as string | null;
  const payload = {
    name: String(formData.get("name") ?? "").trim(),
    base_url: String(formData.get("base_url") ?? "").trim(),
    allowed_domains: parseList(formData.get("allowed_domains")),
    search_keywords: parseList(formData.get("search_keywords")),
    crawl_depth: Number(formData.get("crawl_depth") ?? 1),
    rate_limit: Number(formData.get("rate_limit") ?? 2),
    max_pages: Number(formData.get("max_pages") ?? 50),
    engine: (formData.get("engine") as string) === "playwright" ? "playwright" : "scrapy",
    enabled: formData.get("enabled") === "on",
    notes: (String(formData.get("notes") ?? "").trim() || null) as string | null,
  };

  if (id) {
    await supabase.from("research_sources").update(payload).eq("id", id);
  } else {
    await supabase.from("research_sources").insert(payload);
  }
  revalidatePath("/admin");
}

export async function deleteSource(formData: FormData) {
  const supabase = await requireUser();
  const id = formData.get("id") as string;
  await supabase.from("research_sources").delete().eq("id", id);
  revalidatePath("/admin");
}

// ---- Topics -----------------------------------------------------------

export async function addTopic(formData: FormData) {
  const supabase = await requireUser();
  const name = String(formData.get("name") ?? "").trim();
  if (!name) return;
  const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  await supabase
    .from("research_topics")
    .insert({ name, slug, description: String(formData.get("description") ?? "").trim() || null });
  revalidatePath("/admin");
}

export async function deleteTopic(formData: FormData) {
  const supabase = await requireUser();
  await supabase.from("research_topics").delete().eq("id", formData.get("id") as string);
  revalidatePath("/admin");
}

// ---- Manual scan trigger (queues a run; the local agent picks it up) ----

export async function triggerScan(formData: FormData) {
  const supabase = await requireUser();
  const sourceId = (formData.get("source_id") as string) || null;
  // RLS only permits authenticated inserts that are manual + queued.
  await supabase
    .from("scrape_runs")
    .insert({ source_id: sourceId, trigger: "manual", status: "queued" });
  revalidatePath("/admin");
}

// ---- Grocery: trigger + toggles --------------------------------------

export async function triggerGroceryScan() {
  const supabase = await requireUser();
  // The 'grocery' note tells the local scheduler to run the Flipp collector.
  await supabase
    .from("scrape_runs")
    .insert({ trigger: "manual", status: "queued", notes: "grocery" });
  revalidatePath("/admin");
}

export async function toggleStore(formData: FormData) {
  const supabase = await requireUser();
  await supabase
    .from("grocery_stores")
    .update({ enabled: formData.get("enabled") === "true" })
    .eq("id", formData.get("id") as string);
  revalidatePath("/admin");
}

export async function toggleLocation(formData: FormData) {
  const supabase = await requireUser();
  await supabase
    .from("grocery_locations")
    .update({ enabled: formData.get("enabled") === "true" })
    .eq("id", formData.get("id") as string);
  revalidatePath("/admin");
}

// ---- Auth -------------------------------------------------------------

export async function signOut() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}
