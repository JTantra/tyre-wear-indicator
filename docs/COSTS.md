# Dated Azure retail estimates, not invoices

Evidence snapshot generated2026-11-08T23:58:34UTC, checked9November2026: [verified tariff/usage data](assets/verified-azure-costs.json). First-party price API source URLs and billing documentation are preserved there. Model checkpoint IDs are not prices and operational capability does not prove safety.

| Method | Indicative per image USD | Denominator/scope |
|---|---|---|
| ResNet18 |0.0005171976active compute|onesyntheticAzurestartup/loadsmoke8.61996s|
| MobileNet |0.0005186037active compute|onesyntheticAzurestartup/loadsmoke8.64340s|
| CLIP |0.0006858244active compute|onesyntheticAzurestartup/loadsmoke11.43041s|
| Luna Responsesv2 |0.0002670932–0.0004707494API|25submittedphysicalcases,31868in/5767out|
| Luna Decisionsv2 |0.0001643576–0.0003287152API|25submittedphysicalcases,37354in/0returnedout|
| GPTFT |0.002464API PLUS1.70/hour model hosting|9evalcases,9864in/54out|

Local calculation: seconds×(2vCPU×0.000024USD/s+4GiB×0.000003USD/s). Not measured billed CPU utilization or representative throughput; includes startup/weight loading. Source environment CPU/training timings and local electricity tariff are distinct/unknown. Do not label local hosting free.

Luna short/long-context formula: (input×0.11/0.22 + output×0.55/0.825)/1million/25.25 physical=22 unique binary+2 review+1duplicate. No observed cache read/write. Short/long context threshold and Decisions billing semantics partly unresolved: returned output0is observation, not a no-output-charge contract. Separate full22token means and common9means are retained in the data, not confused with25costmean.

GPT inference uses2.2USD/millioninput and8.8/millionoutput, observed zero cached. Training1162880tokens×0.0275USD/1000=31.9792USD one-off. Hosting24h/day×30days×1.70=1224USD/month even idle.1000images/day:0.0408hosting+0.002464API=0.043264/image;10000/day:0.00408+0.002464=0.006544. Amortized training over30000images adds0.0010659733/image, over300000adds0.0001065973. Training/hosting separate from shared appinfra.

Shared ACA Consumption allocation at snapshot:EastUS,1replica,2CPU/4GiB. Active0.000060USD/s, idle0.000018USD/s.30days2592000s gives46.656USD fully idle through155.52USD fully active BEFORE grants/requests/other infrastructure. Monthly compute=A×0.000060+(2592000−A)×0.000018 where A is total shared active seconds. Allocate across total images/workloads, not three separately billed local hosts. Per-image active estimate is already part of that bill: never add it twice. API methods also use the shared app.

Subscription monthly grant allowances(vCPU180000s,GiB360000s,requests2million) are not assumed unused or reconciled. HTTP request tariff0.40USD/million separately. Excludes storage, PremiumACR, private endpoints/DNS/networking, logging, queue/background work, local training, discounts/tax. Price snapshot is not invoice or spend authorization; current billing may differ. Snapshot190/200calls is dated history only; production ledger never exported.
