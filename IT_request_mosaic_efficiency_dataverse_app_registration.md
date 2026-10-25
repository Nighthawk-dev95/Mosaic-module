# Request: Admin consent + tenant setting for Mosaic Efficiency → Dataverse integration

## Purpose
We're debugging a Power Automate flow that writes 20 calculated columns from the "Mosaic Efficiency" Power BI semantic model into Dynamics Dataverse. The flow's values don't match the Power BI report, and we need API access to query the semantic model's DAX measures directly and compare them against the Dataverse table, so we can isolate where the calculation diverges.

## Already done (self-service, no IT needed)
- App Registration created: `mosaic-efficiency-dataverse-debug`
  - Tenant ID: `1c27a9fe-cae2-4bd8-ad16-1829a656087d`
  - Client (Application) ID: `c1661ec3-d0ab-4128-9b08-f2376aee0c80`
- Client secret generated and stored securely
- API permission added: **Power BI Service → `Tenant.Read.All`** (Application permission) — this is the only read-scoped application permission Power BI Service exposes; actual access stays limited to workspaces the app is added to
- App added as Member/Admin on the **BIPA** workspace (requester is already a workspace Admin)
- Dataverse Application User + read-only security role will be provisioned by requester directly (System Administrator on `org4c0f8903.crm.dynamics.com`, Environment ID `6c898c9d-802f-e712-910b-515198d9a20c`) once the two items below are done

## What's left — needs IT/admin (requester's account lacks the required role)

1. **Grant admin consent** for the `Tenant.Read.All` Application permission on the app registration above. The "Grant admin consent" button is greyed out for the requester's account — needs Global Administrator, Privileged Role Administrator, Cloud Application Administrator, or Application Administrator.
   - Entra ID → App registrations → `mosaic-efficiency-dataverse-debug` → API permissions → Grant admin consent for Radiology Partners Inc.

2. **Enable "Service principals can use Fabric APIs"** tenant setting in the Power BI Admin Portal (Settings → Admin portal → Tenant settings → Developer settings). Scope it to a security group containing this app's service principal if your tenant restricts the setting rather than enabling tenant-wide.

## What we need back
- Confirmation both steps above are complete (no credentials need to be shared back — the requester already holds the client ID/secret)

## Scope note
Read-only access only, limited to the BIPA workspace and this one semantic model. No tenant-wide or write access is being requested.
