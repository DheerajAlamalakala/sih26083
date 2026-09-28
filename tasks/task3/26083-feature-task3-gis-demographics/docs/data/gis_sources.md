\# GIS \& Demographic Data Sources Provenance



\## 1. Official Ward Boundaries (Primary - Government Authoritative)

\- \*\*Source\*\*: TGRAC (Telangana State Remote Sensing Applications Centre)

\- \*\*Endpoint\*\*: https://tgrac.telangana.gov.in/arcgis/rest/services/GHMCHealth\_Folder/GHMC\_Health\_Facilities/MapServer/2

\- \*\*Local Path\*\*: `data/raw/gis/ghmc\_wards\_census\_2021.json`

\- \*\*Quality Flag\*\*: `VERIFIED\_OFFICIAL\_TGRAC\_LAYER`

\- \*\*Source Vintage\*\*: `TGRAC\_2021\_V1`

\- \*\*Status\*\*: ACTIVE (Primary spatial layer used for all 155 GHMC wards)



\## 2. Demographic Baseline Data (Primary Baseline)

\- \*\*Source\*\*: Census India (Office of the Registrar General \& Census Commissioner, India)

\- \*\*Portal URL\*\*: https://censusindia.gov.in/

\- \*\*Dataset Title\*\*: Primary Census Abstract (PCA) - Hyderabad District Baseline

\- \*\*Catalogue ID\*\*: PCA-2011-36-HYDERABAD-WARD

\- \*\*Local Path\*\*: `data/raw/demographics/hyderabad\_census\_2011.csv`

\- \*\*Source Vintage\*\*: `Census 2011 Baseline`

\- \*\*Reliability Note\*\*: Census 2011 metrics serve as historical baseline demographics for vulnerability index normalization and are not presented as live 2026 population counts.



\## 3. Municipal Spatial Data (Secondary - Community Fallback)

\- \*\*Source\*\*: DataMeet Municipal Spatial Data Repository

\- \*\*Repository URL\*\*: https://github.com/datameet/Municipal\_Spatial\_Data

\- \*\*Local Path\*\*: `data/raw/gis/datameet\_hyderabad\_wards.geojson`

\- \*\*Quality Flag\*\*: `DATAMEET\_COMMUNITY\_FALLBACK\_BOUNDARIES`

\- \*\*Source Vintage\*\*: `DATAMEET\_2019\_FALLBACK`

\- \*\*Reliability Note\*\*: Open community-contributed spatial dataset used exclusively as an offline failover layer if the official TGRAC MapServer endpoint is unavailable.

