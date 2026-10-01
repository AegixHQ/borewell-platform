/**
 * The map used for picking a job/rig location and for showing a site.
 *
 * The web app uses Leaflet. react-native-maps is the usual native answer,
 * but it is a native module that needs a Google Maps API key on Android and
 * a config-plugin build - it cannot run in Expo Go, and the registry was
 * unreachable when this was built (see components/ui.js). So this draws the
 * same OpenStreetMap raster tiles the web app uses, as plain <Image>s on a
 * Web-Mercator grid, with a PanResponder for dragging and two buttons for
 * zoom. No dependency, no native build, and the tile URLs are identical to
 * apps/web-app/src/components/SiteMap.jsx's.
 *
 * Tiles come from tile.openstreetmap.org, whose usage policy is meant for
 * modest traffic and asks for an identifying User-Agent that <Image> can't
 * set. Fine for a pilot; before any real launch, point TILE_URL at your own
 * tile server or a keyed provider - it is one line.
 *
 * Note for anyone extending this: POST /v1/resources/match does NOT return
 * lat/lng for the resources it ranks (only distance_km - see
 * packages/contracts/openapi/resource-network.yaml), so nearby rigs cannot
 * be drawn as pins yet. That needs a backend change, not a frontend one.
 */
import { useMemo, useState } from "react";
import { Image, PanResponder, Pressable, Text, View } from "react-native";
import { PILOT_CENTER, colors } from "../theme";
import { Icon } from "./ui";

const TILE = 256;
const TILE_URL = (z, x, y) => `https://tile.openstreetmap.org/${z}/${x}/${y}.png`;

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
      {tiles.map((t) => (
        <Image
          key={t.key}
          source={{ uri: TILE_URL(t.z, t.x, t.y) }}
          style={{ position: "absolute", left: t.left, top: t.top, width: TILE, height: TILE }}
          fadeDuration={120}
        />
      ))}

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

      <Text
        style={{
          position: "absolute",
          left: 8,
          bottom: 6,
          fontSize: 10,
          color: colors.ink2,
          backgroundColor: "rgba(255,255,255,0.72)",
          paddingHorizontal: 5,
          borderRadius: 4,
          overflow: "hidden",
        }}
      >
        © OpenStreetMap
      </Text>
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
