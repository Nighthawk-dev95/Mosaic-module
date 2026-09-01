// "Local" region grouping - translated from the Power BI DAX calculated column
// '0. Cur'[Local], which buckets each Team into one of 6 named regions via a fixed
// SWITCH(TRUE(), Team IN {...}, "X", ...) list. Kept as a plain lookup table here since
// there's no equivalent physical column upstream - Team is the only shared key.
const SPECIAL_OPERATIONS = new Set([
  "ESR", "LFI", "Jefferson", "GLI", "RAI", "RP Cascade", "RP Crossroads", "JR", "DRSRP",
  "RP East Florida", "RP North Florida", "RP Palm Beach", "RP Florida West", "PRA",
  "ESRMH Garnet", "ESRMH Hackensack", "ESRMH Legacy", "ESR Long Island", "ESR Metro Hudson",
  "SEAL Team", "SEAL Legacy", "vRad", "Spec Ops Reserve",
]);

const APEX = new Set([
  "ADI", "ADR", "CRC Central", "CRC NW", "CRC SW", "Midstate", "NEOH", "Rad Alliance",
  "RP Kentucky", "RP Bluegrass", "RAC", "RACSW", "RPKY", "RPBG", "RA", "ADR Legacy", "CRC",
  "Rad Alliance Legacy", "Rad Alliance NorthCrest", "RP Bluegrass Legacy",
]);

const GENESIS = new Set([
  "Coastal", "Greensboro", "MBB", "Northside", "Greensboro Canopy", "RAF", "RP Florida",
  "RP Sandhills", "RP South Carolina", "SOAR", "BOCA", "GR", "NRA", "RASF", "MBB Legacy",
  "MBB Phoebe Putney", "Northside Radiology", "RAF East Coast", "RAF Panhandle",
  "RAF Sarasota", "RAF Tampa", "RAF Tele", "RASF Miami", "RASF Naples", "RP Florida Legacy",
  "RP Florida West",
]);

const MAVERICK = new Set([
  "Advanced Radiology", "Alaska", "CIR", "Desert", "GIMA", "RP SoCal", "IAM", "IAMSE", "MIA",
  "Mountain", "NIR", "RAA", "MXC", "Red Rock", "RIMA", "RP Sol", "RP Sun City", "RP Chicago",
  "RP Forest City", "Saline Valley", "RP Valley Radiologists", "SVDI", "Western Colorado",
  "WIR", "RP IOWA", "GSIA", "SVL", "MR", "DR", "NWIR", "ARSC", "DR Legacy", "DR DRS",
  "IAMSE Hurley", "IAM Marquette", "IAM Midlands", "Lakefront Imaging", "Mountain Legacy",
  "Mountain Yampa", "RP NWIR", "RP SMIL", "RP SoCal Lakewood", "RP SoCal Legacy",
  "RP SoCal Palmdale", "RP Valley", "SVDI Legacy", "SVDI San Ramon", "SMI", "RIMA California",
]);

const TRAILBLAZER = new Set([
  "Access Alexandria", "ARA", "BR Academic", "BR Community", "CIRPA", "Community", "RP Eagle",
  "EBI", "GIA", "Lake Charles", "RP Borderlands", "RP Brazosport", "RP Corpus Christi",
  "RP Dallas", "RP El Paso", "RP Gulf Coast", "RP Houston", "RP Laredo", "RP Victoria", "BR",
  "Slidell", "ACC", "RPNM", "EAG", "RPEP", "RPGC", "RPH", "Other", "EXTHMC",
  "RP Singleton Academic", "RP Singleton Community", "RP Singleton", "Rose",
  "RP North Houston", "Synergy", "Access Lake Charles", "Community Laredo",
  "Community Legacy", "Community Victoria", "Elite", "RP Borderlands Legacy",
  "RP Borderlands Lovelace", "RP Helios",
]);

export const LOCAL_REGIONS = ["Special Operations", "Apex", "Genesis", "Maverick", "Trailblazer", "Matrix"] as const;
export type LocalRegion = (typeof LOCAL_REGIONS)[number];

export function getLocalRegion(team: string | null | undefined): LocalRegion {
  if (!team) return "Matrix";
  if (SPECIAL_OPERATIONS.has(team)) return "Special Operations";
  if (APEX.has(team)) return "Apex";
  if (GENESIS.has(team)) return "Genesis";
  if (MAVERICK.has(team)) return "Maverick";
  if (TRAILBLAZER.has(team)) return "Trailblazer";
  return "Matrix";
}
