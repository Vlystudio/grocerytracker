// Maine location helpers: validate ZIPs and map common town names -> a ZIP.
// Maine ZIP codes run 03901–04992 (they start with "039" or "04").

export function isMaineZip(zip: string): boolean {
  return /^(039\d{2}|04\d{3})$/.test(zip);
}

// Representative ZIP for common Maine towns (lowercase keys). Not exhaustive —
// users can always type a 5-digit ZIP directly.
export const MAINE_TOWNS: Record<string, string> = {
  portland: "04101",
  "south portland": "04106",
  westbrook: "04092",
  falmouth: "04105",
  scarborough: "04074",
  "cape elizabeth": "04107",
  gorham: "04038",
  windham: "04062",
  standish: "04084",
  saco: "04072",
  biddeford: "04005",
  "old orchard beach": "04064",
  kennebunk: "04043",
  wells: "04090",
  york: "03909",
  kittery: "03904",
  sanford: "04073",
  berwick: "03901",
  lewiston: "04240",
  auburn: "04210",
  brunswick: "04011",
  bath: "04530",
  topsham: "04086",
  freeport: "04032",
  yarmouth: "04096",
  augusta: "04330",
  gardiner: "04345",
  waterville: "04901",
  winslow: "04901",
  bangor: "04401",
  brewer: "04412",
  orono: "04473",
  "old town": "04468",
  ellsworth: "04605",
  "bar harbor": "04609",
  belfast: "04915",
  rockland: "04841",
  camden: "04843",
  damariscotta: "04543",
  "boothbay harbor": "04538",
  wiscasset: "04578",
  bridgton: "04009",
  norway: "04268",
  paris: "04281",
  farmington: "04938",
  rumford: "04276",
  skowhegan: "04976",
  "dover-foxcroft": "04426",
  newport: "04953",
  lincoln: "04457",
  houlton: "04730",
  "presque isle": "04769",
  caribou: "04736",
  "fort kent": "04743",
  madawaska: "04756",
  calais: "04619",
  machias: "04654",
  bucksport: "04416",
  greenville: "04441",
  millinocket: "04462",
};

export type ResolvedLocation = { zip: string; label: string };

function titleCase(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Resolve a user's free-text location (ZIP or Maine town) to a ZIP + label.
 * Returns null if it can't be resolved to a Maine location.
 */
export function resolveLocation(input: string): ResolvedLocation | null {
  const raw = input.trim();
  if (!raw) return null;

  // A 5-digit ZIP.
  if (/^\d{5}$/.test(raw)) {
    return isMaineZip(raw) ? { zip: raw, label: raw } : null;
  }

  // A town name — strip a trailing ", ME" / " Maine" etc.
  const key = raw
    .toLowerCase()
    .replace(/,?\s*(me|maine)\.?$/i, "")
    .replace(/\s+/g, " ")
    .trim();

  const zip = MAINE_TOWNS[key];
  return zip ? { zip, label: titleCase(key) } : null;
}
