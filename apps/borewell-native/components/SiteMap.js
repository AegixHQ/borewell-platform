/**
 * The map used for picking a job/rig location and for showing a site.
 *
 * The web app uses Leaflet. This native map deliberately keeps a small
 * dependency-free raster tile renderer: a Web-Mercator grid plus a
 * PanResponder for dragging and buttons for zoom. That preserves the same
 * map interactions without introducing another native mapping module.
 *
 * Tile providers are configured in order. A custom licensed XYZ provider
 * can be supplied with EXPO_PUBLIC_TILE_URL; otherwise the app uses
 * Geoapify's OSM-Carto raster tiles when EXPO_PUBLIC_GEOAPIFY_API_KEY is
 * configured. The public OSM Foundation standard tile server is not used
 * as the app's production tile host because it is best-effort and can block
 * app traffic. When all configured providers fail, the location picker
 * remains usable with its pin and coordinate selection.
 *
 * Keep provider attribution visible and follow the provider's caching and
 * usage requirements. Geoapify's Free plan requires Geoapify and OSM
 * attribution; the app links both labels to their respective sites.
 *
 * Note for anyone extending this: POST /v1/resources/match does NOT return
 * lat/lng for the resources it ranks (only distance_km - see
 * packages/contracts/openapi/resource-network.yaml), so nearby rigs cannot
 * be drawn as pins yet. That needs a backend change, not a frontend one.
 */
import { useMemo, useState } from "react";
import { Image, Linking, PanResponder, Pressable, Text, View } from "react-native";
import { PILOT_CENTER, colors } from "../theme";
import { Icon } from "./ui";

const TILE = 256;
const fill = (tpl, z, x, y) => tpl.replace("{z}", z).replace("{x}", x).replace("{y}", y);
const GEOAPIFY_API_KEY = process.env.EXPO_PUBLIC_GEOAPIFY_API_KEY;
const openAttribution = (url) => {
  Linking.openURL(url).catch((error) => {
    if (__DEV__) console.warn("Could not open map attribution link:", error);
  });
};

// Production-friendly OSM-derived raster provider. Geoapify's osm-carto
// style is a 256px PNG XYZ layer, so it works with this lightweight map
// renderer without adding a native mapping dependency. The public OSMF tile
// server is intentionally not used as an app tile host: it is best-effort,
// has no SLA, and may block application traffic. A custom licensed XYZ
// provider can still be configured ahead of Geoapify.
const PROVIDERS = [
  process.env.EXPO_PUBLIC_TILE_URL && {
    id: "custom",
    url: process.env.EXPO_PUBLIC_TILE_URL,
    credit: process.env.EXPO_PUBLIC_TILE_CREDIT || "© map contributors",
  },
  GEOAPIFY_API_KEY && {
    id: "geoapify",
    url: `https://maps.geoapify.com/v1/tile/osm-carto/{z}/{x}/{y}.png?apiKey=${encodeURIComponent(GEOAPIFY_API_KEY)}`,
    credit: "Powered by Geoapify · © OpenStreetMap contributors",
  },
].filter(Boolean);

// Module-level so a provider that failed once is not retried by every map.
let preferred = 0;

function project(lat, lng, zoom) {
  const scale = TILE * 2 ** zoom;
  const s = Math.min(Math.max(Math.sin((lat * Math.PI) / 180), -0.9999), 0.9999);
  return {
    x: ((lng + 180) / 360) * scale,
    y: (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * scale,
  };
}

function unproject(x, y, zoom) {
  const scale = TILE * 2 ** zoom;
  const n = Math.PI - (2 * Math.PI * y) / scale;
  return {
    lat: (180 / Math.PI) * Math.atan(Math.sinh(n)),
    lng: (x / scale) * 360 - 180,
  };
}

/** Ground resolution, for drawing a radius in km at the right size. */
function metresPerPixel(lat, zoom) {
  return (156543.03392 * Math.cos((lat * Math.PI) / 180)) / 2 ** zoom;
}

export default function SiteMap({
  marker,
  center,
  zoom: initialZoom = 12,
  onMove,
  draggable = false,
  circle,
  areas = [],
  height = 220,
  interactive = true,
}) {
  const start = center || marker || PILOT_CENTER;
  const [zoom, setZoom] = useState(initialZoom);
  const [centre, setCentre] = useState(start);
  const [width, setWidth] = useState(0);
  const [drag, setDrag] = useState({ x: 0, y: 0 });
  const [providerIdx, setProviderIdx] = useState(preferred);
  const provider = PROVIDERS[providerIdx] || null;
  const tileFailed = () => {
    if (providerIdx >= PROVIDERS.length) return;
    // Move the whole map to the next configured provider. If none remains,
    // keep the interactive coordinate picker and pin, but do not display a
    // broken or policy-warning tile as though it were a map.
    preferred = providerIdx + 1;
    setProviderIdx(preferred);
  };

  // Rebuilt whenever what it closes over changes, rather than reading the
  // current values out of refs: the responder handlers are read off the
  // View's props at gesture time, so the newest ones are always the ones
  // that run. The gesture's own dx/dy come in with the release event, so
  // nothing has to be remembered between callbacks either.
  const pan = useMemo(
    () =>
      PanResponder.create({
        onMoveShouldSetPanResponder: (_e, g) => interactive && (Math.abs(g.dx) > 3 || Math.abs(g.dy) > 3),
        onPanResponderMove: (_e, g) => setDrag({ x: g.dx, y: g.dy }),
        onPanResponderRelease: (_e, g) => {
          const p = project(centre.lat, centre.lng, zoom);
          const next = unproject(p.x - g.dx, p.y - g.dy, zoom);
          setDrag({ x: 0, y: 0 });
          setCentre(next);
          // A draggable map reports its centre as the chosen point - the pin
          // is fixed in the middle and the map moves under it. That is easier
          // one-handed than dragging a pin around with the same thumb.
          if (draggable && onMove) onMove(next);
        },
      }),
    [interactive, centre, zoom, draggable, onMove]
  );

  if (width === 0) {
    return <View onLayout={(e) => setWidth(e.nativeEvent.layout.width)} style={{ height, backgroundColor: colors.sunk }} />;
  }

  const c = project(centre.lat, centre.lng, zoom);
  // Top-left corner of the viewport in world pixels, including the live drag.
  const originX = c.x - width / 2 - drag.x;
  const originY = c.y - height / 2 - drag.y;

  const tiles = [];
  const maxTile = 2 ** zoom;
  for (let tx = Math.floor(originX / TILE); tx <= Math.floor((originX + width) / TILE); tx += 1) {
    for (let ty = Math.floor(originY / TILE); ty <= Math.floor((originY + height) / TILE); ty += 1) {
      if (ty < 0 || ty >= maxTile) continue;
      const wrapped = ((tx % maxTile) + maxTile) % maxTile;
      tiles.push({ key: `${zoom}/${tx}/${ty}`, z: zoom, x: wrapped, y: ty, left: tx * TILE - originX, top: ty * TILE - originY });
    }
  }

  const toScreen = (lat, lng) => {
    const p = project(lat, lng, zoom);
    return { left: p.x - originX, top: p.y - originY };
  };

  const pinAt = draggable ? null : marker;

  return (
    <View style={{ height, overflow: "hidden", backgroundColor: colors.sunk }} {...(interactive ? pan.panHandlers : {})}>
      {provider && tiles.map((t) => (
        <Image
          key={t.key}
          source={{ uri: fill(provider.url, t.z, t.x, t.y) }}
          onError={tileFailed}
          style={{ position: "absolute", left: t.left, top: t.top, width: TILE, height: TILE }}
          fadeDuration={120}
        />
      ))}

      {!provider && (
        <View
          pointerEvents="none"
          style={{
            position: "absolute",
            top: 12,
            left: 12,
            right: 58,
            padding: 10,
            borderRadius: 12,
            backgroundColor: colors.surface,
          }}
        >
          <Text style={{ color: colors.ink2, fontSize: 12, lineHeight: 17 }}>
            Map imagery is unavailable. You can still move the map and choose the location using the pin.
          </Text>
        </View>
      )}

      {areas.map((area) => {
        const p = toScreen(area.center_lat, area.center_lng);
        const r = (area.radius_km * 1000) / metresPerPixel(area.center_lat, zoom);
        return (
          <View
            key={area.area_id}
            style={{
              pointerEvents: "none",
              position: "absolute",
              left: p.left - r,
              top: p.top - r,
              width: r * 2,
              height: r * 2,
              borderRadius: r,
              borderWidth: 1.5,
              borderColor: colors.saffron,
              backgroundColor: "rgba(240,167,58,0.14)",
            }}
          />
        );
      })}

      {circle && (
        <CircleOverlay screen={toScreen(circle.lat, circle.lng)} radiusPx={(circle.radiusKm * 1000) / metresPerPixel(circle.lat, zoom)} />
      )}

      {pinAt && <Pin screen={toScreen(pinAt.lat, pinAt.lng)} />}

      {draggable && (
        <View style={{ pointerEvents: "none", position: "absolute", left: width / 2 - 17, top: height / 2 - 40 }}>
          <PinGraphic />
        </View>
      )}

      {interactive && (
        <View style={{ position: "absolute", right: 12, bottom: 12, gap: 8 }}>
          <ZoomButton label="plus" onPress={() => setZoom((z) => Math.min(17, z + 1))} />
          <ZoomButton label="minus" onPress={() => setZoom((z) => Math.max(4, z - 1))} />
        </View>
      )}

      {provider && (
        <Text
          style={{
            position: "absolute",
            left: 8,
            bottom: 6,
            fontSize: 10,
            color: colors.ink2,
            backgroundColor: "rgba(255,255,255,0.82)",
            paddingHorizontal: 5,
            borderRadius: 4,
            overflow: "hidden",
          }}
        >
          {provider.id === "geoapify" ? (
            <>
              <Text onPress={() => openAttribution("https://www.geoapify.com/")} style={{ textDecorationLine: "underline" }}>
                Powered by Geoapify
              </Text>
              {" · "}
              <Text onPress={() => openAttribution("https://www.openstreetmap.org/copyright")} style={{ textDecorationLine: "underline" }}>
                © OpenStreetMap contributors
              </Text>
            </>
          ) : provider.credit}
        </Text>
      )}
    </View>
  );
}

function CircleOverlay({ screen, radiusPx }) {
  return (
    <View
      style={{
        pointerEvents: "none",
        position: "absolute",
        left: screen.left - radiusPx,
        top: screen.top - radiusPx,
        width: radiusPx * 2,
        height: radiusPx * 2,
        borderRadius: radiusPx,
        borderWidth: 2,
        borderColor: colors.chrome,
        borderStyle: "dashed",
      }}
    />
  );
}

function Pin({ screen }) {
  return (
    <View style={{ pointerEvents: "none", position: "absolute", left: screen.left - 17, top: screen.top - 40 }}>
      <PinGraphic />
    </View>
  );
}

function PinGraphic() {
  return (
    <View style={{ alignItems: "center" }}>
      <View
        style={{
          width: 34,
          height: 34,
          borderRadius: 17,
          backgroundColor: colors.saffron,
          borderWidth: 3,
          borderColor: colors.chrome,
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Icon name="pin" size={17} color={colors.chrome} />
      </View>
      <View
        style={{
          width: 0,
          height: 0,
          borderLeftWidth: 5,
          borderRightWidth: 5,
          borderTopWidth: 9,
          borderLeftColor: "transparent",
          borderRightColor: "transparent",
          borderTopColor: colors.chrome,
        }}
      />
    </View>
  );
}

function ZoomButton({ label, onPress }) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        width: 36,
        height: 36,
        borderRadius: 18,
        backgroundColor: pressed ? colors.sunk : "#fff",
        alignItems: "center",
        justifyContent: "center",
      })}
    >
      {label === "plus" ? (
        <Icon name="plus" size={18} color={colors.ink} />
      ) : (
        <View style={{ width: 14, height: 2.2, borderRadius: 2, backgroundColor: colors.ink }} />
      )}
    </Pressable>
  );
}
