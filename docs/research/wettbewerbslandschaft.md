# Wettbewerbslandschaft & Differenzierung — FOREMAN

> Wettbewerbsanalyse · Stand Juni 2026
> Scope: Belastbare, ehrliche Einordnung von FOREMAN gegen die etablierten Plattformen der Industrie-Observability, IIoT/Predictive Maintenance und der neueren „Ask-your-factory-data"-Assistenten. Kein Marketing-Text — eine Analyse, die einem skeptischen Mentor und einem Industriekunden standhält, der die Platzhirsche kennt.
> Vergleichsachsen (vier): **(A)** semantisches Langzeitgedächtnis & Verknüpfung · **(B)** Reasoning statt Regelwerk · **(C)** lokal lauffähig ohne Cloud-Zwang · **(D)** offene Plattform-Schnittstelle statt geschlossene App.
>
> **IP-Hinweis:** Das Gedächtnis-Substrat unter FOREMAN wird hier ausschließlich paraphrasiert beschrieben (biologisch inspirierte Gedächtnisarchitektur, mehrstufige Konsolidierung, semantisches Langzeitgedächtnis, formale Wissensrepräsentation). Keine internen Komponenten-, Library- oder Algorithmen-Namen. Das Dokument ist für Pitch und Capstone freigegeben; es wurde ein Hidden-Term-Scan durchgeführt.

---

## Kurzfazit

Der Markt rund um FOREMAN zerfällt in vier Cluster — Operational Historians, IIoT-Cloud-Plattformen, Predictive-Maintenance-Spezialisten und die neuen generativen „Frag-deine-Fabrik"-Assistenten. Über alle vier zieht sich dieselbe strukturelle Lücke: Es gibt sehr reife Systeme, um Zeitreihen zu speichern, Anomalien zu erkennen und Restlebensdauern zu schätzen — aber keines davon hält ein **konsolidiertes, semantisches Langzeitgedächtnis** vor, das Vorfälle, Lösungen und Werkerbeobachtungen über Zeit, Anlagen und Maschinenklassen hinweg so verdichtet, dass die Frage „Hatten wir das schon mal — und wie haben wir es gelöst?" beantwortbar wird. Die generativen Assistenten klingen am ähnlichsten, sind aber fast durchweg zustandsloses Retrieval im Moment (RAG auf einem Data-Lake plus Cloud-Sprachmodell), das nach der Session vergisst. Die Predictive-Maintenance-Spezialisten sind FOREMAN bei Sensorik, Modellreife und Trainingsdaten klar überlegen — werfen aber genau das Erfahrungswissen weg, das sie nicht aus Sensoren ziehen können (geschätzt rund 60 % des operativen Wissens steckt in Köpfen, nicht in Messwerten). Zwei der ursprünglich angenommenen Wettbewerber existieren 2026 nicht mehr eigenständig: Proficy, ThingWorx und Kepware wurden unter dem PE-Investor TPG zur neuen Firma **Velotic** fusioniert (März 2026), Uptake wird von **Bosch** übernommen. Die ehrliche Konsequenz für den Pitch: FOREMANs verteidigbarster Unterschied liegt auf Achse A (Gedächtnis) und sekundär B (Reasoning), **nicht** auf Achse C (lokal) — denn lokal laufen auch Splunk, C3 AI, Aspen Mtell und Siemens' eigener Copilot — und **nicht** auf Achse D (offene Schnittstelle), denn die offene Schnittstelle wird gerade zur Tischeinsatz-Kommodität.

---

## 1. Cluster: Operational Historians / klassische Observability

Reife Systeme, um operative Daten zu sammeln und zu visualisieren. Stärke auf Achse C (lokal) durchweg hoch, Achse A strukturell leer.

### AVEVA PI System (ehem. OSIsoft PI)

- **Kategorie:** Industrieller Echtzeit-/Zeitreihen-Historian mit Asset-Modellierung (PI Asset Framework).
- **Kern:** Sammeln, Anreichern und Speichern operativer Daten in sub-sekündlicher Granularität; De-facto-Standard-Historian der Prozessindustrie.
- **Stärke:** Riesige installierte Basis (laut AVEVA über zwei Drittel der industriellen Fortune 500), ausgereiftes Connector-Ökosystem, jahrzehntelange Betriebsreife. Gehört heute zu AVEVA / Schneider Electric.
- **Deployment:** Kein Cloud-Zwang. PI Server läuft on-premise; die Cloud-Plattform CONNECT ist als hybride Erweiterung positioniert, nicht als Pflicht.
- **Lücke ggü. FOREMAN:** (A) Speichert Zeitreihen und Ereignisse (Event Frames), aber kein Lösungs-/Erfahrungsgedächtnis — die Kette Vorfall → Diagnose → Lösung wird nicht über die Zeit verknüpft. Ein industrieller Knowledge Graph ist für Q1 2027 *angekündigt*, also noch nicht ausgeliefert. (B) Verknüpfung innerhalb eines Asset-Modells möglich, aber als geschlossenes Ökosystem kritisiert. (C) Stark — hier nicht angreifbar. (D) MCP-Integration auf der AVEVA World 2026 *angekündigt*, nicht verifiziert verfügbar.
- **Quellen:** [AVEVA PI Data Infrastructure](https://www.aveva.com/en/products/pi-data-infrastructure/) · [AVEVA World 2026 (AI/MCP/Knowledge Graph)](https://www.aveva.com/en/about/news/press-releases/2026/aveva-announces-new-capabilities-to-embed-ai-across-industrial-organizations-and-data-infrastructure-at-aveva-world-2026/) · [OSIsoft/AVEVA-Hintergrund](https://en.wikipedia.org/wiki/OSIsoft)
- **Ehrlich gekennzeichnet:** AVEVAs Markenlage ist unsauber — „AVEVA Data Hub" ist faktisch in CONNECT aufgegangen, der Begriff zirkuliert in älteren Quellen weiter. Knowledge Graph und MCP sind Ankündigungen, keine belegte heutige Stärke.

### Splunk (im Industrie-/OT-Einsatz)

- **Kategorie:** Log-/Maschinendaten-Plattform (SIEM/Observability/AIOps), im Industriekontext „Splunk OT Intelligence". Seit März 2024 ein Cisco-Unternehmen.
- **Kern:** Such-, Monitoring- und Analyse über große Log-/Maschinendaten-Mengen; Korrelation zu „Episoden" über ITSI Event Analytics.
- **Stärke:** Marktführende Such-Power und Skalierung; kann air-gapped OT-Quellen anbinden (PLCs, Historians, SCADA via OPC-UA/MQTT/SNMP). Reifes Enterprise-Ökosystem mit RBAC.
- **Deployment:** Kein Cloud-Zwang. Splunk Enterprise läuft on-premise und vollständig air-gapped; Splunk Cloud ist die optionale Managed-Variante.
- **Lücke ggü. FOREMAN:** (A) Speichert Logs/Events/Zeitreihen mit Retention und korreliert sie, verdichtet sie aber nicht zu kuratiertem Erfahrungswissen; „Hatten wir das schon mal?" ist allenfalls als Suchrecherche in Altlogs annäherbar, nicht als strukturiertes Lösungsgedächtnis. (B) Event-Korrelation ja, aber statistisch/regelbasiert, nicht semantisch. (C) Stark (air-gapped). (D) **Splunk MCP Server ist GA** — hier am weitesten von diesem Cluster, aber als Zugriff auf Rohdaten/Suchen, nicht als aggregiertes Erkenntnis-Layer.
- **Quellen:** [Cisco schließt Splunk-Akquisition ab](https://investor.cisco.com/news/news-details/2024/Cisco-Completes-Acquisition-of-Splunk/default.aspx) · [Splunk OT Intelligence](https://www.splunk.com/en_us/solutions/operational-technology-intelligence.html) · [Splunk MCP Server GA](https://community.splunk.com/t5/Product-News-Announcements/GA-Splunk-MCP-Server-Making-Your-Apps-quot-Agent-Ready-quot/ba-p/759935)

### Grafana + InfluxDB / TimescaleDB (Open-Source-Stacks)

- **Kategorie:** Modularer Open-Source-Baukasten (Visualisierung + Zeitreihen-DB), kein einzelner Hersteller.
- **Kern:** Dashboards über Zeitreihen; Grafana als Visualisierungs-Layer, InfluxDB/TimescaleDB als Zeitreihen-Speicher.
- **Stärke:** Offenheit, niedrige Kosten, maximale Flexibilität; breit etabliert für Echtzeit-Visualisierung von Prozessmetriken und OEE.
- **Deployment:** Beste lokale Lauffähigkeit des gesamten Vergleichs — voll selbst-gehostet, voll air-gapped betreibbar.
- **Lücke ggü. FOREMAN:** (A) Praktisch kein Gedächtnis — reine Zeitreihen plus Dashboards, kein Vorfall-/Lösungswissen. (B) Keine anlagenübergreifende Musterverknüpfung out-of-the-box; müsste komplett selbst gebaut werden. (C) Maximal stark. (D) Grafana pflegt ein Open-Source-MCP, aber als Datenabfrage-Brücke, nicht als Erkenntnis-Layer.
- **Quellen:** [Grafana für IIoT/Industrieautomation](https://grafana.com/blog/industrial-iot-visualization-how-grafana-powers-industrial-automation-and-iiot/) · [Grafana MCP Server (Doku)](https://grafana.com/docs/grafana/latest/developer-resources/mcp/)

---

## 2. Cluster: IIoT-/Industrie-Cloud-Plattformen

**Marktbefund 2026 — wichtig:** Drei ursprünglich getrennte Wettbewerber (GE Proficy, PTC ThingWorx, Kepware) wurden vom PE-Investor TPG aufgekauft und am 17. März 2026 unter der neuen Firma **Velotic** zusammengeführt. Das schafft Integrationsunsicherheit, die FOREMAN nutzen kann, ändert aber nichts an deren technischer On-Prem-Reife.

### Siemens Insights Hub (vormals MindSphere)

- **Kategorie:** IIoT-Plattform (Low-Code/Mendix) als Datenschicht der Siemens-„Industrial Operations X"-Strategie. 2023 von MindSphere umbenannt.
- **Kern:** Erfassen, Kontextualisieren und Analysieren von Maschinen-/Anlagendaten; eingebautes OEE und Asset-Health.
- **Stärke:** Native Konnektivität zu Siemens-Hardware (SIMATIC-PLCs, Antriebe), Digital-Twin-Integration, stärkste installierte Basis bei Siemens-Bestandskunden. Industrial-Edge-Produkte sind IEC-62443-4-2- und UL-zertifiziert.
- **Deployment:** Public-SaaS auf AWS und Azure, aber **kein absoluter Cloud-Zwang** — es gibt Insights Hub for Private Cloud (eigenes Rechenzentrum), Cloud Dedicated und Industrial Edge für lokale Analytik.
- **Lücke ggü. FOREMAN:** (A) Kein Beleg für ein anlagen-/zeitübergreifendes Erfahrungsgedächtnis; Fokus auf Streaming-Analytik und OEE. (B) Digital-Twin/Analytik vorhanden, aber kein querschnittliches Muster-Gedächtnis. (C) Teilweise gegeben (Private Cloud/Edge) — echtes Air-Gap unklar belegt. (D) Keine MCP-Belege; Interop über OPC-UA und Mendix-APIs.
- **Quellen:** [Siemens Insights Hub](https://www.siemens.com/en-us/products/insights-hub/) · [Siemens Industrial Edge (IEC 62443)](https://www.siemens.com/en-us/products/industrial-edge/) · [Insights Hub FAQ (Deployment)](https://www.siemens.com/en-us/products/insights-hub/resources/faq/)
- **Ehrlich gekennzeichnet:** Ob die Private-Cloud-Variante echt offline/air-gapped läuft, geht aus öffentlichen Quellen nicht eindeutig hervor — sie adressiert primär Datensouveränität, nicht zwingend vollständige Cloud-Autonomie.

### Velotic — Proficy / ThingWorx / Kepware (ehem. GE Vernova bzw. PTC, jetzt TPG)

- **Kategorie:** Zusammengeführtes Portfolio aus MES/Historian (Proficy), IIoT-Applikationsplattform (ThingWorx) und industrieller Konnektivität (Kepware).
- **Kern:** Produktionsoptimierung, Asset-Monitoring und Maschinenanbindung über heterogene Protokolle.
- **Stärke:** Sehr große installierte Basis (Proficy „40+ Jahre", über 20.000 Kunden) und das stärkste Konnektor-Ökosystem im Vergleich — Kepware spricht 150+ proprietäre Maschinenprotokolle plus OPC-UA. Für reine Maschinenanbindung ist das schwer zu schlagen.
- **Deployment:** Klassisch on-premise-fähig (Proficy-Historian und ThingWorx laufen seit jeher im Werk), neuere Releases hybrid — **kein Cloud-Zwang**.
- **Lücke ggü. FOREMAN:** (A) Historian speichert Telemetrie, ThingWorx modelliert „Things" und Echtzeitzustände — kein zeitübergreifendes Erfahrungs-/Fallgedächtnis. (B) Muster-Logik muss selbst gebaut werden, keine native Querschnitts-Erkennung. (C) Stark (echte On-Prem-Tradition) — hier am wenigsten angreifbar. (D) Keine MCP-Aussage öffentlich; unter Velotic ist die Strategie noch offen.
- **Quellen:** [Velotic-Launch (BusinessWire)](https://www.businesswire.com/news/home/20260316155958/en/Velotic-Launches-to-Shape-Future-of-Industrial-Manufacturing-Software) · [ARC Advisory zu Velotic](https://www.arcweb.com/blog/velotic-launches-independent-industrial-software-company-integrating-proficy-kepware-thingworx) · [GE Vernova: Verkauf Proficy an TPG](https://www.gevernova.com/news/press-releases/ge-vernova-completes-sale-proficyr-software-business) · [PTC: Divestiture ThingWorx/Kepware abgeschlossen](https://www.ptc.com/en/news/2026/ptc-completes-divestiture-of-kepware-and-thingworx-businesses)

### AWS IoT SiteWise & Microsoft Azure IoT (Hyperscaler)

- **Kategorie:** Cloud-Dienste zum Erfassen, Strukturieren und Visualisieren industrieller Daten, mit Edge-Komponenten für lokale Vorverarbeitung.
- **Kern:** Asset-Modelle plus Zeitreihen-Speicher in der Hyperscaler-Cloud; SiteWise Edge bzw. Azure IoT Operations als Edge-Datenebene.
- **Stärke:** Tiefe Cloud-Ökosystem-Integration, OT-Protokolle (OPC-UA, Modbus, EtherNet/IP), elastische Skalierung. SiteWise Edge läuft sogar auf Siemens Industrial Edge.
- **Deployment — zentral:** **Hier liegt der Cloud-Zwang am stärksten vor.** SiteWise Edge kann bei Internetausfall lokal weiterpuffern, ist aber als Vorverarbeitung *für* die Cloud konzipiert, nicht für dauerhaft cloud-freien Betrieb. Azure bindet über Azure Arc zwingend an die Cloud-Steuerungsebene. Air-Gap ist bei beiden nicht das Designziel.
- **Lücke ggü. FOREMAN:** (A) Kein semantisches Fall-Gedächtnis (Telemetrie/Asset-Daten). (B) Keine native Querschnitts-Mustererkennung — man baut Analytik aus weiteren Cloud-Diensten selbst. (C) **Schwächster Punkt — strukturell cloud-zentriert; hier ist FOREMANs lokales Argument am stärksten.** (D) Keine native MCP-Schnittstelle; Integration über Cloud-APIs.
- **Quellen:** [AWS IoT SiteWise (Doku)](https://docs.aws.amazon.com/iot-sitewise/latest/userguide/what-is-sitewise.html) · [AWS Greengrass in disconnected environments](https://aws.amazon.com/blogs/publicsector/deploying-mission-critical-edge-applications-with-aws-iot-greengrass-in-disconnected-environments/) · [Microsoft: Azure IoT Operations](https://azure.microsoft.com/en-us/products/iot-operations) · [Microsoft Learn: Azure-IoT-Dienste (Feature-complete-Status)](https://learn.microsoft.com/en-us/azure/iot/iot-services-and-technologies)
- **Ehrlich gekennzeichnet:** Microsoft hat seine alte IoT-Suite 2024–2026 stark zusammengeräumt (Azure IoT Central endet zum 31. März 2027; mehrere Dienste „feature-complete") und setzt auf Azure IoT Operations. Das ist Konsolidierung, keine Schwäche im Kernangebot.

---

## 3. Cluster: Predictive-Maintenance-Spezialisten

FOREMANs nächste Verwandte — und der ehrlichste Vergleichsmaßstab. Im Kern durchweg: **Sensordaten → Anomalie/Restlebensdauer → Alert/Work-Order.** Bei Sensorik, Modellreife und Trainingsdaten sind sie FOREMAN überlegen; das strukturelle Defizit liegt im Gedächtnis für das, was nicht aus Sensoren kommt.

### Augury

- **Kategorie:** Full-Stack Machine Health — eigene Vibrations-/Temperatur-/Magnetfeld-Sensorik plus KI-Diagnostik plus menschliche Reliability-Experten.
- **Stärke:** Proprietäres Sensorik-Ökosystem (edge-AI-native Sensoren) und Trainingsdaten aus Millionen Maschinenstunden. Unicorn (>1 Mrd. USD Bewertung, ~369 Mio. USD Funding). **Hier ist FOREMAN klar unterlegen.**
- **Deployment:** Edge-AI im Sensor, aber die volle Diagnostik läuft in Augurys Cloud — faktisch Cloud-Zwang plus Hardware-/Abo-Bindung.
- **Lücke ggü. FOREMAN:** (A) Reine Diagnostik auf Sensordaten, kein durchsuchbares Vorfall-/Lösungsgedächtnis inkl. Werkerbeobachtung. (B) Musterübertragung innerhalb der eigenen Sensorflotte, nicht als anlagenübergreifendes Wissen. (C) Cloud-gebunden. (D) Geschlossenes Hardware+SaaS-Ökosystem.
- **Quellen:** [Augury: $75M Funding, $1B Bewertung](https://www.augury.com/media-center/press/augury-announces-75-million-of-funding-and-maintains-1b-valuation-as-it-accelerates-leadership-in-industrial-ai-solutions/) · [Augury Halo / Edge-AI-Sensor](https://www.augury.com/media-center/press/augury-introduces-the-first-industrial-grade-edge-ai-native-machine-health-sensing-platform/)

### Senseye Predictive Maintenance (Siemens)

- **Kategorie:** Software-only Predictive Maintenance, sensor-agnostisch. Von Siemens 2022 übernommen, heute in Xcelerator/Insights Hub integriert.
- **Stärke:** Arbeitet mit vorhandenen Daten (Historians/IoT/Legacy) ohne Hardware-Zwang, enterprise-skaliert (bis 10.000+ Maschinen), lernt aus Instandhalter-Verhalten. Rückhalt des Siemens-Ökosystems.
- **Deployment:** Explizit Cloud-SaaS — Cloud-Zwang, aber keine Sensor-Bindung.
- **Lücke ggü. FOREMAN:** (A) Lernt aus Instandhalter-*Verhalten* (näher an FOREMAN als die Sensorik-Reinen), bleibt aber Forecast-Priorisierung, kein durchsuchbares Lösungs-/Fallgedächtnis. (B) Anlagenübergreifend als statistisches Modell, nicht als konsolidiertes Wissen. (C) Cloud-gebunden. (D) Geschlossen ins Siemens-Ökosystem.
- **Quellen:** [Siemens übernimmt Senseye (2022)](https://press.siemens.com/global/en/pressrelease/siemens-acquires-senseye-predictive-maintenance-and-asset-intelligence-industrial) · [Senseye Cloud Application (Siemens)](https://www.siemens.com/en-us/products/industrial-digitalization-services/senseye-cloud-application/)

### C3 AI (Reliability / Readiness)

- **Kategorie:** Enterprise-AI-Plattform mit PdM-Produkten auf der C3 Agentic AI Platform; zunehmend agentische Root-Cause-Analyse.
- **Stärke:** Plattform-Tiefe, validierte Modellbibliothek, große Referenzen (Shell >13.000 Anlagen; US-Air-Force-Rahmen bis 450 Mio. USD). Nähert sich als einziger im Cluster konzeptionell dem Reasoning-Gedanken.
- **Deployment:** Baut für Cloud, On-Prem **und** air-gapped (Government/regulierte Industrien) — **kein Cloud-Zwang.** Das ist die schwächste Stelle von FOREMANs „lokal"-Argument gegenüber C3 AI.
- **Lücke ggü. FOREMAN:** (A) Trotz agentischer Root-Cause primär Sensordaten/Asset-Telemetrie — kein durchsuchbares Langzeitgedächtnis für Werkerbeobachtungen und Lösungswissen. (B) Anlagenübergreifende Muster ja (Plattform-Stärke). (C) On-Prem/air-gapped vorhanden — hier nicht angreifbar. (D) Proprietär/geschlossen, keine offene MCP-Schnittstelle belegt. Zudem schwergewichtig und integrationsaufwendig.
- **Quellen:** [C3 AI & Shell: agentische Reliability-AI](https://c3.ai/c3-ai-and-shell-expand-collaboration-scaling-reliability-ai-deployment-across-global-asset-operations/) · [C3 AI Deployment (cloud/on-prem/air-gapped)](https://c3.ai/c3-agentic-ai-platform/platform-services/deployment/)

### Aspen Mtell (AspenTech / Emerson)

- **Kategorie:** AI-gestützte prescriptive + predictive Maintenance im APM-Portfolio; „Failure Agents", die Fehlermuster lernen und automatisch Work-Orders ins EAM schicken. AspenTech seit Anfang 2025 Voll-Tochter von Emerson.
- **Stärke:** Modellreife und Branchenfokus Prozessindustrie (Öl/Gas, Chemie, Mining) — erkennt Fehlermuster bis zu 90 Tage im Voraus, tief in Prozess-/EAM-Kontext eingebettet. **Bei reiner Vorhersagereife ist FOREMAN unterlegen.**
- **Deployment:** Klassisch APM/on-premise-fähig (prozessindustrie-typisch), starke Bindung an den AspenTech/Emerson-Stack — kein hartes Cloud-Argument dagegen.
- **Lücke ggü. FOREMAN:** (A) Trotz „prescriptive" Muster-/Agenten-Logik auf Sensor-/Prozessdaten, kein semantisches Vorfall-Gedächtnis über freie Werkerbeobachtungen. (B) Agenten werden über Anlagen repliziert, nicht zu Querschnitts-Wissen verdichtet. (C) On-Prem-fähig. (D) Geschlossenes EAM/APM-Ökosystem.
- **Quellen:** [Aspen Mtell (AspenTech)](https://www.aspentech.com/en/products/apm/aspen-mtell) · [Emerson: Vollübernahme AspenTech (SEC 8-K, Jan 2025)](https://www.sec.gov/Archives/edgar/data/0001897982/000114036125001939/ny20042057x1_ex99-1.htm)

### Uptake (→ Bosch, 2026)

- **Kategorie:** KI-Predictive-Analytics, zuletzt Fokus kommerzielle Fahrzeugflotten. Das frühere Chicago-Startup hatte massive Schwierigkeiten (Personalabbau ~50 % vom Peak) und wird 2026 von Bosch übernommen, eingebunden in dessen Telematik-Ökosystem.
- **Lücke ggü. FOREMAN:** (A) Predictive Analytics + Empfehlungen, kein semantisches Lösungsgedächtnis. (C) Cloud-orientiert. (D) Geht in geschlossenes Bosch-Ökosystem auf. Der Verlauf (Startup-Krise → Aufkauf) ist selbst ein Signal: reine PdM trägt allein schwer eigenständig.
- **Quellen:** [Bosch übernimmt Uptake (Automotive Fleet)](https://www.automotive-fleet.com/10256459/bosch-to-acquire-ai-predictive-maintenance-startup-uptake-technologies) · [Uptake-Personalabbau (Crain's)](https://www.chicagobusiness.com/john-pletz-technology/uptake-cuts-more-jobs-headcount-down-about-half-peak)
- **Ehrlich gekennzeichnet:** Eine Quelle nennt zusätzlich einen Käufer „Prescient" (Jan 2026) — mit hoher Wahrscheinlichkeit eine Namensverwechslung mit einer gleichnamigen Firma; der belastbar dokumentierte Vorgang für Uptake Technologies ist die Bosch-Übernahme.

---

## 4. Cluster: Neuere LLM-/„Ask-your-factory-data"-Ansätze

Der Cluster, der FOREMAN am ähnlichsten klingt — und deshalb am schärfsten abzugrenzen ist. Durchgängiges Muster: **Cloud-Sprachmodell + Retrieval/RAG auf einem Data-Lake/Knowledge-Graph + Tool-Calling.** Das ist Retrieval im Moment, kein konsolidiertes Langzeitgedächtnis. Die Branche selbst benennt 2026 genau diese Lücke: RAG ist „stateless retrieval … forgets everything when the session ends".

### Cognite Atlas AI — der gefährlichste Vertreter

- **Kategorie:** Agentic-AI-Schicht („Industrial Agents") auf Cognite Data Fusion, mit Low-Code-Agent-Builder und kuratierter Modell-Library. Major Release Sept. 2025.
- **Tiefe:** Am tiefsten im Feld. Cognite formuliert die Architektur selbst als „Industrial Knowledge Graph = foundational memory, Atlas AI = execution layer" — deutlich mehr als ein Chat-Layer.
- **Deployment:** „any cloud, any LLM", EU-AI-Act-konform — aber Context Augmented Generation läuft prominent über Azure OpenAI, de facto Cloud-Sprachmodell. Echte air-gapped On-Prem-Lauffähigkeit nicht belegt.
- **Lücke ggü. FOREMAN:** (A) Der „Knowledge Graph als Memory" ist **strukturiertes Stamm-/Asset-Wissen, kein sich über Zeit verdichtendes Erfahrungsgedächtnis.** (B) Sehr stark (Datenfusion). (C) Cloud-Sprachmodell-Abhängigkeit. (D) Agent-API offen.
- **Quellen:** [Cognite Atlas AI](https://www.cognite.com/en/product/atlas) · [Cognite: Atlas AI Major Release](https://www.cognite.com/en/company/newsroom/cognite-atlas-ai-drives-customer-momentum-with-new-major-release)

### Siemens Industrial Copilot — der einzige mit echtem On-Prem

- **Kategorie:** Gen-AI-Copilot über Operations-/Dokumentdaten; übersetzt Fehlercodes in Klartext, analysiert Telemetrie. Von thyssenkrupp adoptiert.
- **Tiefe:** Architektur im Kern rekursives RAG (iteratives Retrieval) plus Vektor-Embeddings — sophisticated, aber Retrieval, nicht persistentes Gedächtnis.
- **Deployment:** Stärkstes On-Prem-Angebot im Cluster — On-Premises-Hardware-Software-Bundle, volle Datensouveränität, **keine Internetverbindung nötig.**
- **Lücke ggü. FOREMAN:** (C) gelöst (on-prem!) — **hier kann FOREMAN nicht über „lokal" differenzieren, sondern nur über das Gedächtnis.** (A) Kein konsolidiertes Langzeitgedächtnis, reines (rekursives) RAG. (B) Begrenzt auf das Siemens-Ökosystem.
- **Quellen:** [Siemens Industrial Copilot (thyssenkrupp)](https://press.siemens.com/global/en/pressrelease/siemens-industrial-copilot-expanded-adopted-thyssenkrupp) · [Insights Hub Production Copilot (Bad Neustadt)](https://blogs.sw.siemens.com/insights-hub/2025/02/26/siemens-insights-hub-production-copilot-being-tested-by-the-bad-neustadt-electric-motors-factory-ewn/)

### UptimeAI — der einzige mit „Lernen über Zeit"

- **Kategorie:** „AI Expert" plus AI Reasoning Agents (seit März 2026), orchestriert Ingenieurs-Skills für Schwer-Asset-Industrien.
- **Tiefe:** Am nächsten an echtem Reasoning, „continuously learning from outcomes". **Aber:** Es ist ML-/Modell-Lernen an Asset-Verhalten (Drift-Anpassung), **kein semantisch-narratives, abfragbares Langzeitgedächtnis über Ereignisse und Anlagen hinweg.** Hier muss FOREMAN sauber abgrenzen: adaptives Modell ≠ semantisches Gedächtnis.
- **Deployment:** AWS-Marketplace-gelistet, cloud-orientiert; echtes On-Prem nicht belegt.
- **Quellen:** [UptimeAI: AI Reasoning Agents](https://www.uptimeai.com/resources/uptimeai-launches-ai-reasoning-agents/) · [UptimeAI Products](https://www.uptimeai.com/products/)

### Hyperscaler-Assistenten & Tulip — dünner als das Marketing

- **AWS IoT SiteWise Assistant:** NL-Query auf Operationsdaten, Architektur explizit RAG (Kendra + Bedrock + Amazon Q) — Retrieval im Moment plus Cloud-Sprachmodell, kein Gedächtnis. [Quelle](https://aws.amazon.com/about-aws/whats-new/2024/11/aws-iot-sitewise-generative-ai-powered-industrial-assistant)
- **Microsoft Factory Operations Agent:** Marketing ≠ Substanz — die dedizierten Manufacturing-/Factory-Agent-Previews wurden Mai/Juni 2025 *deprecated*; der Weg läuft jetzt über generisches Copilot Studio plus Partner (Accenture/Avanade „Agentic Factory", GA erst später 2026). 2026 kein fertiges Produkt. [Quelle](https://learn.microsoft.com/en-us/industry/manufacturing/whats-new)
- **Google Manufacturing Data Engine + Gemini:** NL-Dashboards ohne SQL, real im Einsatz (GE Appliances), aber Cloud-Zwang (GCP/Gemini), kein Langzeitgedächtnis. [Quelle](https://cloud.google.com/solutions/manufacturing-data-engine)
- **Tulip Frontline Copilot:** Überwiegend Build-/Dokumenten-Assistent plus Dashboard-NL, kein Reasoning-/Memory-Anspruch — dünnster Chat-Layer der Liste. [Quelle](https://tulip.co/blog/announcing-frontline-copilot/)

### MCP-Trend (Achse D) verdichtet sich

Splunk MCP **GA**, AVEVA **angekündigt**, Inductive Automation (Ignition) **PoC mit Release 2026**, Microsoft Copilot Studio konsumiert MCP. Anfang 2026 über 500 öffentliche MCP-Server. **Konsequenz: Eine offene MCP-Schnittstelle ist Tischeinsatz, kein Verkaufsargument mehr.** FOREMAN bietet sie an, differenziert sich aber nicht darüber.

---

## 5. Differenzierungs-Matrix

FOREMAN gegen die vier Cluster entlang der vier Achsen. Bewertung aus Sicht „wo hat FOREMAN einen echten Unterschied".

| Achse | Historians (PI, Splunk, Grafana) | IIoT-Cloud (Siemens, Velotic, Hyperscaler) | PdM-Spezialisten (Augury, Senseye, C3, Mtell) | LLM-Assistenten (Cognite, Siemens Copilot, UptimeAI, Hyperscaler) | **FOREMAN** |
|---|---|---|---|---|---|
| **A — semant. Langzeitgedächtnis & Verknüpfung** | Zeitreihen/Events, kein Lösungsgedächtnis | Telemetrie/Asset-Daten, kein Fallgedächtnis | Sensor-Anomalie/RUL, wirft Werkerwissen weg | RAG im Moment / statischer Knowledge Graph, vergisst nach Session | **Konsolidiertes Gedächtnis aus Sensordaten + Werkerbeobachtungen + Lösungen, anlagenübergreifend** |
| **B — Reasoning statt Regelwerk** | Schwellwerte/Korrelation | überwiegend Schwellwerte/Analytik | ML-Anomalie/RUL, C3 & UptimeAI agentisch | RAG-Antwort, teils agentisch | **Reasoning über konsolidierte Muster im Kontext** |
| **C — lokal ohne Cloud-Zwang** | stark (alle) | **gemischt** (Hyperscaler Cloud-Zwang, Velocity/Siemens on-prem) | **gemischt** (C3/Mtell on-prem, Augury/Senseye Cloud) | **gemischt** (Siemens Copilot on-prem, Rest Cloud) | **lokal lauffähig als Default** |
| **D — offene Schnittstelle statt App** | Splunk MCP GA, Rest aufholend | meist geschlossen, keine MCP-Belege | geschlossene OEM-Ökosysteme | MCP kommodifiziert sich | **offene Schnittstelle (kein Alleinstellungsmerkmal)** |

Lesart der Matrix: Achse A ist die einzige, auf der **alle vier Cluster gleichzeitig** eine Lücke haben. Achse B ist ein echter, aber zunehmend bestrittener Unterschied (C3 AI und UptimeAI bewegen sich darauf zu). Achse C trägt **nur gegen den jeweils cloud-gebundenen Teil** jedes Clusters, nicht pauschal. Achse D ist kein Differenzierer mehr.

---

## 6. Wo die Großen stärker sind (ehrlicher Gegenabschnitt)

Eine Differenzierung, die die Stärke des Gegners leugnet, fällt im ersten kritischen Gespräch. Deshalb explizit, wo FOREMAN heute klar unterlegen ist:

**Installierte Basis und Reife.** AVEVA PI sitzt in über zwei Dritteln der industriellen Fortune 500, Proficy hat 40+ Jahre und 20.000+ Kunden, Siemens hat seine gesamte Hardware-Kundschaft. FOREMAN hat einen Showcase und ein Capstone. Das ist kein Vergleich, den man gewinnen will — man umgeht ihn.

**Sensorik und Modellreife.** Augury baut eigene edge-AI-Sensoren und sitzt auf Millionen Maschinenstunden Trainingsdaten. Aspen Mtell sagt Fehler bis zu 90 Tage im Voraus voraus. C3 AI überwacht bei einem einzigen Kunden über 13.000 Anlagen. Diese Vorhersagereife ist jahrelang trainiert und nicht aus dem Stand zu replizieren. FOREMAN sollte sich nie als „bessere Predictive Maintenance" positionieren — da verliert es.

**Connector-Ökosysteme.** Kepware (jetzt Velotic) spricht 150+ proprietäre Maschinenprotokolle. PI und Proficy haben jahrzehntelang gereifte Konnektoren. FOREMANs Anbindung ist solide (OPC-UA, MQTT, Modbus, S7), aber jung.

**Lokale Lauffähigkeit ist kein Alleinstellungsmerkmal.** Splunk Enterprise läuft air-gapped, C3 AI und Aspen Mtell laufen on-premise, Siemens Industrial Copilot läuft als On-Prem-Bundle ohne Internet. Wer behauptet „nur wir laufen lokal", wird sofort widerlegt.

**Skalierung, Support, Zertifizierung.** Siemens Industrial Edge ist IEC-62443-4-2- und UL-zertifiziert; die Großen haben globale Support-Organisationen, SLAs und Compliance-Apparate. FOREMAN hat das noch nicht und sollte Zertifizierung als Roadmap-Punkt benennen, nicht als vorhandene Eigenschaft.

Die ehrliche Gesamtaussage: Die Großen sind überlegen bei allem, was mit Masse, Reife und physikalischer Messung zu tun hat. FOREMANs Raum ist nicht „dasselbe besser", sondern „das, was strukturell keiner von ihnen tut".

---

## 7. Pitch-fertige Formulierungen

Aktualisierte, belegte Kurzantworten als Erweiterung der bestehenden Briefing-Antwort. Jede hält der direkten Rückfrage „und warum kann X das nicht auch?" stand.

**„Warum nicht einfach Splunk?"**
Splunk ist hervorragend, wenn man wissen will, *was gerade passiert* — es durchsucht riesige Log- und Maschinendatenmengen und korreliert Ereignisse, auch air-gapped. Was Splunk nicht tut: aus diesen Ereignissen ein verdichtetes Erfahrungswissen bilden. „Hatten wir dieses Lagergeräusch schon mal, und wie wurde es damals gelöst?" beantwortet Splunk nur als Suchanfrage in Altlogs, nicht als kuratiertes Lösungsgedächtnis. FOREMAN ist die Schicht, die genau das aufbaut — und die Werkerbeobachtung, die in keinem Log steht, mitkonsolidiert.

**„Warum nicht AVEVA PI System?"**
PI ist der Standard-Historian und unschlagbar im Sammeln und Speichern von Zeitreihen. Aber ein Historian speichert Messwerte, kein gelöstes Problem. PI verknüpft nicht Vorfall mit Diagnose mit Lösung über die Zeit — der dafür gedachte Knowledge Graph ist bei AVEVA für 2027 angekündigt, nicht ausgeliefert. FOREMAN setzt nicht *gegen* den Historian an, sondern *darüber*: Es liest die Daten und baut das Gedächtnis, das der Historian nicht hat.

**„Warum nicht Siemens Insights Hub / Industrial Copilot?"**
Siemens ist der ernsthafteste Vergleich, weil der Industrial Copilot tatsächlich lokal läuft, ohne Internet. Der Unterschied liegt also nicht beim „lokal", sondern beim Gedächtnis: Der Copilot ist im Kern Retrieval — er holt im Moment die passende Doku oder Telemetrie und formuliert eine Antwort. Nach der Frage behält er nichts. FOREMAN hält ein konsolidiertes Langzeitgedächtnis, das über Wochen, Anlagen und Maschinenklassen hinweg verdichtet und verknüpft. Lokal *und* mit Gedächtnis — diese Kombination hat im Moment keiner der Großen.

**„Warum nicht Augury / C3 AI / Aspen Mtell?"**
Die sind FOREMAN bei der reinen Ausfallvorhersage überlegen — eigene Sensorik, jahrelang trainierte Modelle. Aber ihr Output endet beim Alarm oder der Work-Order. Sie konsolidieren nicht das, was sie nicht aus Sensoren ziehen können: die Beobachtung des Werkers, den Lösungsweg, das „beim letzten Mal war es die andere Charge Schmierfett". Geschätzt rund 60 % des operativen Wissens steckt in Köpfen, nicht in Messwerten — und genau das geht beim Renteneintritt verloren. FOREMAN ist die Gedächtnis-Schicht für dieses Wissen, nicht der nächste Anomalie-Detektor.

**„Macht das nicht jeder Copilot / Cognite längst?"**
Sie klingen ähnlich, weil alle „frag deine Fabrikdaten" verkaufen. Technisch ist es fast überall dasselbe: ein Cloud-Sprachmodell durchsucht im Moment einen Data-Lake und vergisst danach. Selbst Cognites „Memory" ist ein statischer Wissensgraph aus Stammdaten, kein Erfahrungsgedächtnis, das über Zeit lernt und verdichtet. FOREMANs Substrat ist genau dafür gebaut — und es läuft lokal, während die generativen Assistenten fast durchweg am Cloud-Sprachmodell hängen.

---

## 8. Bottom-Line

**Die zwei bis drei verteidigbarsten Differenzierungs-Aussagen** (mit jeweils stärkstem Beleg):

1. **Semantisches Langzeitgedächtnis statt Speicher oder Retrieval-im-Moment.** Das ist der einzige Unterschied, der gegen *alle vier* Cluster gleichzeitig hält. Stärkster Beleg: Die LLM-Assistenten — der direkteste Konkurrent — sind nachweislich zustandsloses RAG („forgets everything when the session ends"), und selbst Cognites „foundational memory" ist ein statischer Wissensgraph, kein Erfahrungsgedächtnis. Die PdM-Spezialisten werfen das Werkerwissen strukturell weg.

2. **Lokal lauffähig *und* mit Gedächtnis — die Kombination.** Einzeln ist beides nicht einzigartig (Siemens läuft lokal, Cognite hat einen Wissensgraphen). Aber niemand bietet beides zusammen: Die Systeme mit der stärksten Gedächtnis-/Reasoning-Anmutung hängen am Cloud-Sprachmodell; das stärkste lokale System (Siemens Copilot) ist reines Retrieval. Diese Kreuzung ist FOREMANs eigentlicher Raum.

3. **Reasoning über konsolidierte Muster statt fest verdrahteter Schwellwerte** — als sekundäres, ehrlich zu führendes Argument. Verteidigbar gegen Historians und klassische IIoT-Plattformen, aber mit dem Vermerk, dass C3 AI und UptimeAI sich in diese Richtung bewegen; nicht als Alleinstellung überziehen.

**Ein bis zwei Aussagen, die man bewusst NICHT machen sollte**, weil sie zu angreifbar sind:

1. **Nicht: „Nur FOREMAN läuft lokal / ohne Cloud."** Sofort widerlegbar — Splunk Enterprise (air-gapped), C3 AI (air-gapped), Aspen Mtell (on-prem) und Siemens Industrial Copilot (On-Prem-Bundle ohne Internet) laufen ebenfalls lokal. „Lokal" nur in Kombination mit „Gedächtnis" führen, nie als isoliertes Alleinstellungsmerkmal.

2. **Nicht: „FOREMAN sagt Ausfälle besser/früher voraus als die PdM-Spezialisten."** Da verliert FOREMAN gegen Sensorik (Augury), Modellreife (Aspen Mtell, 90 Tage Vorlauf) und Trainingsdaten-Basis. FOREMAN ist kein besserer Anomalie-Detektor, sondern die Gedächtnis-Schicht über der Vorhersage. Ebenso wenig sollte man „offene MCP-Schnittstelle" als Differenzierer verkaufen — das wird gerade Kommodität (Splunk GA, viele folgen).

---

*Quellen sind als Inline-Links bei den jeweiligen Aussagen hinterlegt. Recherchestand Juni 2026. Wo die Faktenlage dünn oder widersprüchlich ist (AVEVA-Markenlage, Siemens-Private-Cloud-Air-Gap, Uptake-Käufer), ist das im Text als „ehrlich gekennzeichnet" markiert.*
