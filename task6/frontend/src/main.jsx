import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "./styles.css";

const API = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api/v1";
const WEATHER_API = "https://api.open-meteo.com/v1/forecast";

const LEVELS = ["CRITICAL", "HIGH", "MODERATE", "LOW"];
const LEVEL_META = {
  CRITICAL: { label: "Critical", className: "critical", description: "Immediate protective response" },
  HIGH: { label: "High", className: "high", description: "Strong protective response" },
  MODERATE: { label: "Moderate", className: "moderate", description: "Prepare and monitor closely" },
  LOW: { label: "Low", className: "low", description: "Routine monitoring" },
};

const fmt = (value, digits = 0) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(digits);
};

const levelClass = (level) => String(level || "LOW").toLowerCase();

function Stat({ label, value, unit, hint, icon }) {
  return (
    <div className="stat-card">
      <div className="stat-icon">{icon}</div>
      <div className="stat-copy">
        <span>{label}</span>
        <strong>{value}{unit && <small>{unit}</small>}</strong>
        {hint && <em>{hint}</em>}
      </div>
    </div>
  );
}

function RiskBadge({ level, compact = false }) {
  const meta = LEVEL_META[level] || LEVEL_META.LOW;
  return <span className={`risk-badge ${meta.className} ${compact ? "compact" : ""}`}><i />{meta.label}</span>;
}

function centroidFromGeoJSON(geojson) {
  const points = [];
  const collect = (coords) => {
    if (!Array.isArray(coords)) return;
    if (coords.length >= 2 && typeof coords[0] === "number" && typeof coords[1] === "number") {
      points.push(coords);
      return;
    }
    coords.forEach(collect);
  };
  if (geojson?.geometry?.coordinates) collect(geojson.geometry.coordinates);
  if (!points.length) return null;
  const lon = points.reduce((sum, p) => sum + p[0], 0) / points.length;
  const lat = points.reduce((sum, p) => sum + p[1], 0) / points.length;
  return { lat, lon };
}

function formatWeatherTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: true,
  });
}

function App() {
  const [summary, setSummary] = useState(null);
  const [wards, setWards] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [selected, setSelected] = useState(null);
  const [selectedDay, setSelectedDay] = useState(1);
  const [alertFilter, setAlertFilter] = useState("ALL");
  const [expandedAction, setExpandedAction] = useState(null);
  const [notify, setNotify] = useState("");
  const [notificationSending, setNotificationSending] = useState(false);
  const [notificationResult, setNotificationResult] = useState(null);
  const [status, setStatus] = useState("Connecting to demo backend…");
  const [loadingWard, setLoadingWard] = useState(false);
  const [weatherFixture, setWeatherFixture] = useState(null);
  const [liveWeather, setLiveWeather] = useState(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [weatherError, setWeatherError] = useState("");
  const [pipelineStage, setPipelineStage] = useState(1);
  const [detailPanel, setDetailPanel] = useState(null);
  const [notificationConfig, setNotificationConfig] = useState({ provider: "Twilio", sms_configured: false, recipient_roles: [], mode: "not_configured" });
  const [recipientRole, setRecipientRole] = useState("municipal_ward_officer");

  useEffect(() => {
    Promise.all([
      fetch(`${API}/demo/summary`).then((r) => r.json()),
      fetch(`${API}/wards`).then((r) => r.json()),
      fetch(`${API}/alerts`).then((r) => r.json()),
      fetch(`${API}/forecast`).then((r) => r.json()),
      fetch(new URL("../../demo_data/weather_fixture.json", import.meta.url)).then((r) => r.json()),
      fetch(`${API}/notifications/config`).then((r) => r.json()),
    ]).then(([s, w, a, f, weather, notificationData]) => {
      setSummary(s);
      setWards(w);
      setAlerts(a);
      setForecast(f.records || []);
      setWeatherFixture(weather);
      setNotificationConfig(notificationData || { provider: "Twilio", sms_configured: false, recipient_roles: [], mode: "not_configured" });
      const firstConfigured = (notificationData?.recipient_roles || []).find((r) => r.configured);
      if (firstConfigured) setRecipientRole(firstConfigured.role);
      setStatus("Demo backend connected • live weather ready");
    }).catch(() => {
      setStatus("Backend or demo fixture unavailable • start FastAPI and Vite");
    });
  }, []);

  const byWard = useMemo(() => {
    const map = {};
    forecast.forEach((row) => {
      if (!map[row.ward_id]) map[row.ward_id] = [];
      map[row.ward_id].push(row);
    });
    return map;
  }, [forecast]);

  const alertByWard = useMemo(() => {
    const map = {};
    alerts.forEach((row) => {
      if (!map[row.ward_id] || row.forecast_day < map[row.ward_id].forecast_day) map[row.ward_id] = row;
    });
    return map;
  }, [alerts]);

  const filteredAlerts = useMemo(() => {
    if (alertFilter === "ALL") return alerts;
    return alerts.filter((a) => a.alert_level === alertFilter);
  }, [alerts, alertFilter]);

  const selectedForecast = useMemo(() => {
    if (!selected) return [];
    return selected.forecast || byWard[selected.ward.ward_id] || [];
  }, [selected, byWard]);

  const selectedDayRow = selectedForecast.find((row) => Number(row.forecast_day) === Number(selectedDay)) || selectedForecast[0];
  const selectedAlert = selectedDayRow ? alerts.find((a) => a.ward_id === selectedDayRow.ward_id && Number(a.forecast_day) === Number(selectedDayRow.forecast_day)) : null;
  const fixtureWeather = weatherFixture?.hourly_records?.[weatherFixture.hourly_records.length - 1];
  const selectedFeature = useMemo(() => {
    if (!wards || !selected) return null;
    return wards.features?.find((feature) => feature.properties?.ward_id === selected.ward.ward_id) || null;
  }, [wards, selected]);
  const weatherLocation = useMemo(() => centroidFromGeoJSON(selectedFeature), [selectedFeature]);

  useEffect(() => {
    let cancelled = false;
    if (!weatherLocation) {
      setLiveWeather(null);
      setWeatherError("");
      return undefined;
    }

    const loadLiveWeather = async () => {
      setWeatherLoading(true);
      setWeatherError("");
      try {
        const params = new URLSearchParams({
          latitude: weatherLocation.lat.toFixed(5),
          longitude: weatherLocation.lon.toFixed(5),
          current: "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m,shortwave_radiation,weather_code",
          daily: "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max,weather_code",
          forecast_days: "5",
          timezone: "Asia/Kolkata",
        });
        const response = await fetch(`${WEATHER_API}?${params.toString()}`);
        if (!response.ok) throw new Error("Live weather request failed");
        const data = await response.json();
        if (!cancelled) setLiveWeather(data);
      } catch {
        if (!cancelled) {
          setLiveWeather(null);
          setWeatherError("Live weather unavailable — showing demo fixture values where available.");
        }
      } finally {
        if (!cancelled) setWeatherLoading(false);
      }
    };

    loadLiveWeather();
    const timer = setInterval(loadLiveWeather, 10 * 60 * 1000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [weatherLocation]);

  const currentLive = liveWeather?.current;
  const liveDaily = liveWeather?.daily;
  const weatherSourceLabel = liveWeather ? "LIVE · Open-Meteo" : "DEMO FIXTURE";

  const selectWard = async (wardId) => {
    setLoadingWard(true);
    setNotify("");
    setExpandedAction(null);
    try {
      const response = await fetch(`${API}/wards/${encodeURIComponent(wardId)}`);
      if (!response.ok) throw new Error("Ward unavailable");
      const detail = await response.json();
      setSelected(detail);
      setSelectedDay(1);
    } catch {
      setSelected(null);
      setStatus("Unable to load selected ward from backend");
    } finally {
      setLoadingWard(false);
    }
  };

  const sendNotification = async (channel, action = selectedAlert) => {
    if (!action || notificationSending) return;
    const recipientLabel = notificationConfig.recipient_roles.find((r) => r.role === recipientRole)?.label || "selected stakeholder";
    setNotificationSending(true);
    setNotificationResult(null);
    setNotify(`Sending ${channel === "sms" ? "SMS" : channel} to ${recipientLabel}…`);
    try {
      const response = await fetch(`${API}/notifications/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ward_id: action.ward_id, channel, recipient_role: recipientRole }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || `Notification failed (HTTP ${response.status})`);
      const successText = result.twilio_trial_mode
        ? `SMS accepted by Twilio trial template for ${result.recipient_label}. Message ID: ${result.message_sid}.`
        : `SMS accepted by Twilio for ${result.recipient_label}. Message ID: ${result.message_sid}.`;
      const success = { kind: "success", text: successText, sid: result.message_sid, status: result.message_status };
      setNotificationResult(success);
      setNotify(`✓ ${success.text}`);
    } catch (error) {
      const failure = { kind: "error", text: `SMS not sent: ${error.message}` };
      setNotificationResult(failure);
      setNotify(failure.text);
    } finally {
      setNotificationSending(false);
    }
  };


  const triggerAction = async (action) => {
    try {
      const response = await fetch(`${API}/actions/trigger`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ward_id: action.ward_id, forecast_day: Number(action.forecast_day) }),
      });
      const result = await response.json();
      setNotify(`Action available for ${result.action.ward_id}, Day ${result.action.forecast_day}.`);
    } catch {
      setNotify("Canonical action record could not be loaded.");
    }
  };

  const styleFeature = (feature) => {
    const id = feature?.properties?.ward_id;
    const alert = alertByWard[id];
    const selectedId = selected?.ward?.ward_id;
    const level = alert?.alert_level || "LOW";
    return {
      color: selectedId === id ? "#123b5d" : ({ LOW: "#4f8a62", MODERATE: "#d9a441", HIGH: "#d56b2d", CRITICAL: "#c83f4a" }[level]),
      weight: selectedId === id ? 4 : 1.5,
      fillOpacity: selectedId === id ? 0.62 : 0.38,
    };
  };

  const onEachWard = (feature, layer) => {
    const id = feature.properties?.ward_id;
    const alert = alertByWard[id];
    layer.bindTooltip(`${id} • ${alert?.alert_level || "NO ALERT"}`, { sticky: true });
    layer.on({
      click: () => selectWard(id),
      mouseover: () => layer.setStyle({ weight: 3, fillOpacity: 0.58 }),
      mouseout: () => layer.setStyle(styleFeature(feature)),
    });
  };

  const levelCounts = LEVELS.reduce((acc, level) => {
    acc[level] = alerts.filter((a) => a.alert_level === level).length;
    return acc;
  }, {});

  const pipelineAction = selectedAlert || selected?.actions?.find((a) => Number(a.forecast_day) === Number(selectedDay));
  const pipelineData = useMemo(() => ({
    stage1: {
      location: weatherLocation,
      source: liveWeather ? "Open-Meteo live weather" : "Supplied offline/demo fixture",
      temperature: currentLive?.temperature_2m ?? fixtureWeather?.temperature_c,
      humidity: currentLive?.relative_humidity_2m ?? fixtureWeather?.relative_humidity_pct,
      wind: currentLive?.wind_speed_10m ?? fixtureWeather?.wind_speed_ms,
      solar: currentLive?.shortwave_radiation ?? fixtureWeather?.solar_radiation_wm2,
      rain: currentLive?.precipitation,
      apparent: currentLive?.apparent_temperature,
    },
    stage2: selectedDayRow ? {
      thermal: selectedDayRow.thermal_stress_0_100,
      vulnerability: selectedDayRow.vulnerability_0_100 ?? selected?.ward?.vulnerability_0_100,
      hospitalization: selectedDayRow.hospitalization_risk_0_100,
      mortality: selectedDayRow.mortality_risk_0_100,
      hospitalizationLevel: selectedDayRow.hospitalization_risk_level,
      mortalityLevel: selectedDayRow.mortality_risk_level,
      drivers: selectedDayRow.drivers || [],
      model: selectedDayRow.model_version,
      source: selectedDayRow.source_type,
      quality: selectedDayRow.quality_flag,
      synthetic: selectedDayRow.is_synthetic,
    } : null,
    stage3: pipelineAction ? {
      alert: pipelineAction.alert_level,
      ward: pipelineAction.ward_id,
      day: pipelineAction.forecast_day,
      advisory: pipelineAction.advisory_text,
      actions: pipelineAction.municipal_actions || [],
      notificationRequired: pipelineAction.notification_required,
      notificationStatus: pipelineAction.notification_status,
      rule: pipelineAction.rule_version,
    } : null,
  }), [weatherLocation, liveWeather, currentLive, fixtureWeather, selectedDayRow, selected, pipelineAction]);

  const liveForecastForDay = (day) => {
    if (!liveDaily?.time?.[day - 1]) return null;
    return {
      date: liveDaily.time[day - 1],
      max: liveDaily.temperature_2m_max?.[day - 1],
      min: liveDaily.temperature_2m_min?.[day - 1],
      rain: liveDaily.precipitation_sum?.[day - 1],
      wind: liveDaily.wind_speed_10m_max?.[day - 1],
    };
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark">R</div>
          <div>
            <div className="eyebrow">WARD-LEVEL HEAT INTELLIGENCE</div>
            <h1>RAKSHA <span>— Extreme Heatwave Early Warning System</span></h1>
            <p>Current conditions → forecast → health risk → alert → municipal action</p>
          </div>
        </div>
        <div className="connection-state"><span className="pulse" />{status}</div>
      </header>

      <section className="hero-grid">
        <div className="hero-card current-hero">
          <div className="section-kicker"><span className="live-dot" /> {weatherSourceLabel} WEATHER</div>
          <div className="hero-main">
            <div>
              <div className="hero-temperature">
                {selected ? fmt(currentLive?.temperature_2m ?? fixtureWeather?.temperature_c, 1) : "—"}<sup>°C</sup>
              </div>
              <div className="hero-label">{selected ? `${selected.ward.ward_name} · current temperature` : "Select a ward for location-based live weather"}</div>
              <div className="timestamp">
                {selected && currentLive ? `Updated ${formatWeatherTime(liveWeather?.current?.time)}` : selected ? "Live weather not available" : "No ward selected"}
              </div>
            </div>
            <div className="hero-weather-note">
              {selected ? <><strong>{liveWeather ? "Live weather" : "Demo fallback"}</strong><br />Location: {weatherLocation ? `${weatherLocation.lat.toFixed(3)}°, ${weatherLocation.lon.toFixed(3)}°` : "—"}</> : <>Click a ward on the map<br /><strong>Weather follows the selected location</strong></>}
            </div>
          </div>
          {weatherError && <div className="weather-warning">{weatherError}</div>}
          {weatherLoading && selected && <div className="weather-loading">Refreshing live weather…</div>}
        </div>
        <div className="hero-card alert-hero">
          <div className="section-kicker">SYSTEM ALERT OVERVIEW</div>
          <div className="alert-summary-row">
            {LEVELS.map((level) => (
              <button key={level} className={`alert-count ${levelClass(level)} ${alertFilter === level ? "active" : ""}`} onClick={() => setAlertFilter(alertFilter === level ? "ALL" : level)}>
                <strong>{levelCounts[level] || 0}</strong><span>{LEVEL_META[level].label}</span>
              </button>
            ))}
          </div>
          <button className={`filter-reset ${alertFilter === "ALL" ? "selected" : ""}`} onClick={() => setAlertFilter("ALL")}>Show all alerts</button>
        </div>
      </section>

      <section className="weather-strip">
        <Stat label="Humidity" value={fmt(currentLive?.relative_humidity_2m ?? fixtureWeather?.relative_humidity_pct, 1)} unit="%" hint={liveWeather ? "Live relative humidity" : "Demo fixture"} icon="💧" />
        <Stat label="Wind speed" value={fmt(currentLive?.wind_speed_10m ?? fixtureWeather?.wind_speed_ms, 1)} unit=" m/s" hint={liveWeather ? "Live at 10 m" : "Demo fixture"} icon="🌬️" />
        <Stat label="Solar radiation" value={fmt(currentLive?.shortwave_radiation ?? fixtureWeather?.solar_radiation_wm2, 0)} unit=" W/m²" hint={liveWeather ? "Live shortwave radiation" : "Demo fixture"} icon="☀️" />
        <Stat label="Precipitation" value={fmt(currentLive?.precipitation, 1)} unit=" mm" hint={liveWeather ? "Current precipitation" : "Live weather only"} icon="🌧️" />
        <Stat label="Thermal stress" value={fmt(selectedDayRow?.thermal_stress_0_100, 1)} unit=" / 100" hint={selected ? `${selected.ward.ward_name} · Day ${selectedDayRow?.forecast_day || selectedDay}` : "Select a ward for canonical forecast"} icon="🌡️" />
        <Stat label="Health risk" value={selectedAlert?.alert_level || "—"} hint={selected ? "Canonical action level" : "Select a ward"} icon="🛡️" />
      </section>

      <section className="pipeline-panel panel-card">
        <div className="pipeline-header">
          <div><div className="section-kicker">THE RAKSHA DIFFERENCE</div><h2>Three-stage early-warning pipeline</h2><p>Follow the actual data journey: <strong>observe → assess → respond</strong>. Expand a stage to inspect the values behind the decision.</p></div>
          <span className="pipeline-note">No frontend risk recalculation</span>
        </div>
        <div className="pipeline-steps">
          {[
            {n:1, title:"Environmental Exposure", sub:"Weather & exposure inputs", icon:"◉"},
            {n:2, title:"Thermal & Health Risk", sub:"Canonical Task 4 outputs", icon:"◈"},
            {n:3, title:"Alert & Response", sub:"Canonical Task 5 action engine", icon:"◆"},
          ].map((step, i) => (
            <React.Fragment key={step.n}>
              <button className={`pipeline-step ${pipelineStage === step.n ? "active" : ""}`} onClick={() => setPipelineStage(step.n)} aria-label={`Open stage ${step.n}: ${step.title}`}>
                <span className="pipeline-number">{step.n}</span><span className="pipeline-icon">{step.icon}</span><span className="pipeline-step-copy"><strong>{step.title}</strong><small>{step.sub}</small></span><span className="pipeline-arrow">{pipelineStage === step.n ? "−" : "+"}</span>
              </button>
              {i < 2 && <span className="pipeline-connector" aria-hidden="true">→</span>}
            </React.Fragment>
          ))}
        </div>
        {!selected ? (
          <div className="pipeline-empty"><span>⌖</span><div><strong>Select a ward to inspect the complete pipeline</strong><small>The same ward selection drives weather, canonical risk and municipal response.</small></div></div>
        ) : (
          <div className="pipeline-detail">
            {pipelineStage === 1 && <div className="stage-content">
              <div className="stage-heading"><div><span>STAGE 1</span><h3>Environmental exposure inputs</h3><p>Observed/live weather values available for the selected ward. These are displayed, not scientifically recalculated here.</p></div><button className="detail-button" onClick={() => setDetailPanel("stage1")}>View data details</button></div>
              <div className="stage-metrics">
                <div><span>Temperature</span><strong>{fmt(pipelineData.stage1.temperature,1)}<small> °C</small></strong></div>
                <div><span>Relative humidity</span><strong>{fmt(pipelineData.stage1.humidity,1)}<small> %</small></strong></div>
                <div><span>Wind speed</span><strong>{fmt(pipelineData.stage1.wind,1)}<small> m/s</small></strong></div>
                <div><span>Solar radiation</span><strong>{fmt(pipelineData.stage1.solar,0)}<small> W/m²</small></strong></div>
                <div><span>Precipitation</span><strong>{pipelineData.stage1.rain == null ? "—" : fmt(pipelineData.stage1.rain,1)}<small>{pipelineData.stage1.rain == null ? " not available" : " mm"}</small></strong></div>
                <div><span>Apparent temperature</span><strong>{pipelineData.stage1.apparent == null ? "—" : fmt(pipelineData.stage1.apparent,1)}<small>{pipelineData.stage1.apparent == null ? " not available" : " °C"}</small></strong></div>
              </div>
              <div className="stage-source"><span className={liveWeather ? "source-live" : "source-demo"}>●</span>{pipelineData.stage1.source} · Location follows the selected ward geometry.</div>
            </div>}
            {pipelineStage === 2 && <div className="stage-content">
              <div className="stage-heading"><div><span>STAGE 2</span><h3>Thermal & health risk assessment</h3><p>Canonical Task 4 values returned by the existing backend. No frontend risk calculation is performed.</p></div><button className="detail-button" onClick={() => setDetailPanel("stage2")}>View model details</button></div>
              <div className="stage-metrics risk-stage">
                <div><span>Thermal stress</span><strong>{fmt(pipelineData.stage2?.thermal,1)}<small> / 100</small></strong></div>
                <div><span>Vulnerability</span><strong>{fmt(pipelineData.stage2?.vulnerability,1)}<small> / 100</small></strong></div>
                <div><span>Hospitalization risk</span><strong>{fmt(pipelineData.stage2?.hospitalization,1)}<small> / 100</small></strong></div>
                <div><span>Mortality risk</span><strong>{fmt(pipelineData.stage2?.mortality,2)}<small> / 100</small></strong></div>
              </div>
              <div className="driver-row"><span>Drivers considered</span>{(pipelineData.stage2?.drivers || []).slice(0,5).map((d) => <button key={d} onClick={() => setDetailPanel("stage2")}>{d.replaceAll("_", " ")}</button>)}</div>
              <div className="stage-source"><span className="source-canonical">●</span>Source: {pipelineData.stage2?.source || "canonical backend"} · Model: {pipelineData.stage2?.model || "—"} · Quality: {pipelineData.stage2?.quality || "—"}{pipelineData.stage2?.synthetic ? " · Synthetic demo record" : ""}</div>
            </div>}
            {pipelineStage === 3 && <div className="stage-content">
              <div className="stage-heading"><div><span>STAGE 3</span><h3>Decision, alert & municipal response</h3><p>The existing Task 5 action engine converts canonical risk outputs into an operational response.</p></div><button className="detail-button" onClick={() => setDetailPanel("stage3")}>View response details</button></div>
              <div className="stage-response-grid">
                <div className={`decision-card ${levelClass(pipelineData.stage3?.alert)}`}><span>FINAL ALERT</span><strong>{pipelineData.stage3?.alert || "—"}</strong><small>Ward {pipelineData.stage3?.ward || "—"} · Day {pipelineData.stage3?.day || "—"}</small></div>
                <div className="response-copy"><span>Advisory</span><p>{pipelineData.stage3?.advisory || "No canonical action record for this ward/day."}</p></div>
              </div>
              <div className="response-actions"><span>Municipal response</span>{(pipelineData.stage3?.actions || []).map((item) => <button key={item} onClick={() => triggerAction(pipelineAction)}>{item}<b>›</b></button>)}{pipelineData.stage3?.notificationRequired && <><label className="recipient-select compact"><span>SMS RECIPIENT</span><select value={recipientRole} onChange={(e) => setRecipientRole(e.target.value)}>{notificationConfig.recipient_roles.map((r) => <option key={r.role} value={r.role}>{r.label}</option>)}</select></label><button disabled={!notificationConfig.sms_configured || !notificationConfig.recipient_roles.some((r) => r.role === recipientRole && r.configured)} onClick={() => sendNotification("sms", pipelineAction)}>Send SMS <b>›</b></button></>}</div>
              <div className="stage-source"><span className="source-canonical">●</span>Rule: {pipelineData.stage3?.rule || "—"} · Notification: {pipelineData.stage3?.notificationStatus || "—"}{pipelineData.stage3?.notificationRequired ? " · Notification required" : ""}</div>
            </div>}
          </div>
        )}
      </section>

      <main className="dashboard-grid">
        <section className="map-card panel-card">
          <div className="panel-title-row">
            <div><div className="section-kicker">SPATIAL VIEW</div><h2>Ward alert map</h2><p>Click any ward to update every related panel and its live weather location.</p></div>
            <div className="map-legend">{LEVELS.map((level) => <span key={level}><i className={`legend-dot ${levelClass(level)}`} />{LEVEL_META[level].label}</span>)}</div>
          </div>
          <div className="map-wrap">
            {wards ? <MapContainer center={[17.39, 78.48]} zoom={10} scrollWheelZoom>
              <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <GeoJSON key={selected?.ward?.ward_id || "all"} data={wards} style={styleFeature} onEachFeature={onEachWard} />
            </MapContainer> : <div className="map-loading">Loading ward geometry…</div>}
            {loadingWard && <div className="map-overlay">Loading ward details…</div>}
          </div>
        </section>

        <aside className="selected-card panel-card">
          <div className="panel-title-row"><div><div className="section-kicker">WARD FOCUS</div><h2>{selected?.ward?.ward_name || "Select a ward"}</h2></div>{selectedAlert && <RiskBadge level={selectedAlert.alert_level} />}</div>
          {!selected ? (
            <div className="empty-state"><div className="empty-icon">⌖</div><h3>Choose a ward on the map</h3><p>The selected ward, live weather, canonical forecast, health-risk indicators, alert and municipal actions will appear here.</p></div>
          ) : (
            <>
              <div className="ward-meta"><span>{selected.ward.zone_name}</span><span>Vulnerability {fmt(selected.ward.vulnerability_0_100, 1)}/100</span></div>
              <div className="selected-live-strip"><span className="live-pill"><i /> LIVE WEATHER</span><strong>{fmt(currentLive?.temperature_2m ?? fixtureWeather?.temperature_c, 1)} °C</strong><span>Feels like {fmt(currentLive?.apparent_temperature, 1)} °C</span></div>
              <div className="selected-alert-box">
                <div><span className="mini-label">DAY {selectedDayRow?.forecast_day || selectedDay} ALERT</span><strong>{selectedAlert?.advisory_text || "No canonical action record for this ward/day."}</strong></div>
                {selectedAlert && <RiskBadge level={selectedAlert.alert_level} compact />}
              </div>
              <div className="day-tabs" role="tablist">
                {[1, 2, 3, 4, 5].map((day) => <button key={day} className={Number(selectedDay) === day ? "active" : ""} onClick={() => setSelectedDay(day)}>Day {day}</button>)}
              </div>
              {selectedDayRow ? <div className="risk-metrics">
                <div><span>Thermal stress</span><strong>{fmt(selectedDayRow.thermal_stress_0_100, 1)}<small>/100</small></strong></div>
                <div><span>Hospitalization risk</span><strong>{fmt(selectedDayRow.hospitalization_risk_0_100, 1)}<small>/100</small></strong></div>
                <div><span>Mortality risk</span><strong>{fmt(selectedDayRow.mortality_risk_0_100, 2)}<small>/100</small></strong></div>
              </div> : <div className="no-data">No canonical forecast record is available for this ward.</div>}
              <div className="selected-actions">
                <button className="primary-button" disabled={!selectedAlert} onClick={() => selectedAlert && triggerAction(selectedAlert)}>Open canonical action</button>
                <button className="secondary-button" disabled={!selectedAlert || !notificationConfig.sms_configured} onClick={() => selectedAlert && sendNotification("sms", selectedAlert)}>Send SMS</button>
              </div>
              {notify && <div className="toast">{notify}</div>}
            </>
          )}
        </aside>
      </main>

      <section className="panel-card forecast-panel">
        <div className="panel-title-row">
          <div><div className="section-kicker">5-DAY OUTLOOK</div><h2>{selected ? `${selected.ward.ward_name} · live weather + canonical health outlook` : "5-day weather & health outlook"}</h2><p>Weather forecast is live location data. Thermal stress and health-risk values remain the existing canonical backend outputs.</p></div>
          {selected && <span className="data-chip">{liveWeather ? "LIVE WEATHER + CANONICAL RISK" : "DEMO WEATHER + CANONICAL RISK"}</span>}
        </div>
        {selected ? <div className="forecast-cards">
          {[1, 2, 3, 4, 5].map((day) => {
            const row = selectedForecast.find((r) => Number(r.forecast_day) === day);
            const action = alerts.find((a) => a.ward_id === selected.ward.ward_id && Number(a.forecast_day) === day);
            const weatherDay = liveForecastForDay(day);
            return <button key={day} className={`forecast-card ${Number(selectedDay) === day ? "active" : ""}`} onClick={() => setSelectedDay(day)}>
              <div className="forecast-top"><span>DAY {day}</span>{action && <RiskBadge level={action.alert_level} compact />}</div>
              <strong>{weatherDay ? `${fmt(weatherDay.max, 0)}°C` : "—"}<small>{weatherDay ? ` max · ${fmt(weatherDay.min, 0)}°C min` : " live weather"}</small></strong>
              <div className="forecast-risks"><span>Thermal stress <b>{row ? fmt(row.thermal_stress_0_100, 1) : "—"}</b>/100</span><span>Hospital <b>{row ? fmt(row.hospitalization_risk_0_100, 1) : "—"}</b>/100</span><span>Rain <b>{weatherDay ? fmt(weatherDay.rain, 1) : "—"}</b> mm</span></div>
              <div className="forecast-date">{weatherDay?.date ? new Date(`${weatherDay.date}T12:00:00+05:30`).toLocaleDateString("en-IN", { day: "2-digit", month: "short" }) : row?.valid_time_utc ? new Date(row.valid_time_utc).toLocaleDateString() : "No data"}</div>
            </button>;
          })}
        </div> : <div className="empty-inline">Select a ward to load its location-based live weather and five canonical forecast days.</div>}
      </section>

      <section className="panel-card action-panel">
        <div className="panel-title-row action-heading">
          <div><div className="section-kicker">RESPONSE CENTRE</div><h2>Municipal actions</h2><p>Interactive action records from the existing alert engine. Expand a card for details and controls.</p></div>
          <div className="filter-group">{["ALL", ...LEVELS].map((level) => <button key={level} className={alertFilter === level ? "active" : ""} onClick={() => setAlertFilter(level)}>{level === "ALL" ? "All" : LEVEL_META[level].label}</button>)}<span className={`twilio-status ${notificationConfig.sms_configured ? "ready" : "off"}`}>{notificationConfig.sms_configured ? "● Twilio SMS ready" : "○ Twilio SMS not configured"}</span></div>
        </div>
        <div className="action-grid">
          {filteredAlerts.length ? filteredAlerts.map((action) => {
            const open = expandedAction === `${action.ward_id}-${action.forecast_day}`;
            return <article key={`${action.ward_id}-${action.forecast_day}`} className={`action-card ${levelClass(action.alert_level)} ${open ? "expanded" : ""}`}>
              <button className="action-summary" onClick={() => setExpandedAction(open ? null : `${action.ward_id}-${action.forecast_day}`)}>
                <div className="action-level"><RiskBadge level={action.alert_level} compact /><span>Day {action.forecast_day}</span></div>
                <strong>{action.ward_id}</strong>
                <span className="action-chevron">{open ? "−" : "+"}</span>
              </button>
              {open && <div className="action-details">
                <div className="detail-grid"><div><span>Related ward</span><b>{action.ward_id}</b></div><div><span>Priority / alert</span><b>{LEVEL_META[action.alert_level]?.label}</b></div><div><span>Notification</span><b>{action.notification_status}</b></div><div><span>Rule version</span><b>{action.rule_version}</b></div></div>
                <p className="advisory">{action.advisory_text}</p>
                <div className="action-list"><span>Municipal actions</span>{action.municipal_actions.map((item) => <button key={item} onClick={() => triggerAction(action)}>{item}<b>›</b></button>)}</div>
                <div className="control-row"><button className="primary-button" onClick={() => selectWard(action.ward_id)}>Open ward</button><button className="secondary-button" onClick={() => triggerAction(action)}>Check action</button>{action.notification_required && <button className="secondary-button" disabled={!notificationConfig.sms_configured} onClick={() => sendNotification("sms", action)}>Send SMS</button>}</div>
              </div>}
            </article>;
          }) : <div className="empty-inline">No action records match this alert filter.</div>}
        </div>
      </section>

      {detailPanel && selected && <div className="detail-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setDetailPanel(null)}>
        <section className="detail-drawer" role="dialog" aria-modal="true" aria-label="Pipeline details">
          <div className="drawer-head"><div><span>RAKSHA PIPELINE DETAILS</span><h2>{detailPanel === "stage1" ? "Stage 1 · Environmental exposure" : detailPanel === "stage2" ? "Stage 2 · Thermal & health risk" : "Stage 3 · Alert & response"}</h2></div><button onClick={() => setDetailPanel(null)} aria-label="Close details">×</button></div>
          {detailPanel === "stage1" && <div className="drawer-body"><p className="drawer-intro">Every available live weather field is shown with its unit. No unavailable value is fabricated.</p><div className="drawer-list">{[["Temperature",pipelineData.stage1.temperature,"°C"],["Relative humidity",pipelineData.stage1.humidity,"%"],["Wind speed",pipelineData.stage1.wind,"m/s"],["Solar radiation",pipelineData.stage1.solar,"W/m²"],["Precipitation",pipelineData.stage1.rain,"mm"],["Apparent temperature",pipelineData.stage1.apparent,"°C"]].map(([l,v,u])=><div key={l}><span>{l}</span><strong>{v == null ? "Not available" : `${fmt(v, l === "Solar radiation" ? 0 : 1)} ${u}`}</strong></div>)}</div><div className="drawer-note">Source: {pipelineData.stage1.source}. Ward location: {weatherLocation ? `${weatherLocation.lat.toFixed(5)}°, ${weatherLocation.lon.toFixed(5)}°` : "—"}.</div></div>}
          {detailPanel === "stage2" && <div className="drawer-body"><p className="drawer-intro">These values are passed through from the existing health-risk dataset and backend adapter.</p><div className="drawer-list">{[["Thermal stress",pipelineData.stage2?.thermal,"/100"],["Vulnerability",pipelineData.stage2?.vulnerability,"/100"],["Hospitalization risk",pipelineData.stage2?.hospitalization,"/100"],["Mortality risk",pipelineData.stage2?.mortality,"/100"],["Hospitalization level",pipelineData.stage2?.hospitalizationLevel,""],["Mortality level",pipelineData.stage2?.mortalityLevel,""]].map(([l,v,u])=><div key={l}><span>{l}</span><strong>{v == null ? "—" : `${typeof v === "number" ? fmt(v, l.includes("Mortality risk") ? 2 : 1) : v} ${u}`}</strong></div>)}</div><div className="drawer-note"><b>Drivers:</b> {(pipelineData.stage2?.drivers || []).join(", ") || "Not supplied"}<br/><b>Model:</b> {pipelineData.stage2?.model || "—"} · <b>Quality:</b> {pipelineData.stage2?.quality || "—"} · <b>Source type:</b> {pipelineData.stage2?.source || "—"}</div></div>}
          {detailPanel === "stage3" && <div className="drawer-body"><p className="drawer-intro">This response is the existing Task 5 action-engine record for the selected ward and forecast day.</p><div className="drawer-list">{[["Alert level",pipelineData.stage3?.alert,""],["Related ward",pipelineData.stage3?.ward,""],["Forecast day",pipelineData.stage3?.day,""],["Notification status",pipelineData.stage3?.notificationStatus,""],["Rule version",pipelineData.stage3?.rule,""],["Notification required",pipelineData.stage3?.notificationRequired ? "Yes" : "No",""]].map(([l,v,u])=><div key={l}><span>{l}</span><strong>{v == null ? "—" : `${v} ${u}`}</strong></div>)}</div><div className="drawer-advisory"><span>ADVISORY</span><p>{pipelineData.stage3?.advisory || "—"}</p></div><div className="drawer-actions">{pipelineData.stage3?.notificationRequired && <><label className="recipient-select"><span>NOTIFY STAKEHOLDER</span><select value={recipientRole} onChange={(e) => setRecipientRole(e.target.value)}>{notificationConfig.recipient_roles.map((r) => <option key={r.role} value={r.role}>{r.label}{r.configured ? " · configured" : " · not configured"}</option>)}</select></label><button className="primary-button" disabled={notificationSending || !notificationConfig.sms_configured || !notificationConfig.recipient_roles.some((r) => r.role === recipientRole && r.configured)} onClick={() => sendNotification("sms", pipelineAction)}>{notificationSending ? "Sending…" : "Send real SMS"}</button></>}<button className="secondary-button" onClick={() => triggerAction(pipelineAction)}>Verify canonical action</button></div></div>}
        </section>
      </div>}

      <footer><strong>RAKSHA</strong> keeps the supplied Task 1/3/4/5 artifacts and existing API integration unchanged. Live weather is fetched for the selected ward from Open-Meteo; thermal stress, health risk, alerts and municipal actions remain canonical backend values. If live weather is unavailable, the dashboard falls back to the supplied offline/demo fixture. Stage 3 SMS uses Twilio only when configured; otherwise the UI never claims that a real message was sent.</footer>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
