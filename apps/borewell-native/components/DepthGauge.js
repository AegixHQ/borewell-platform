/**
 * Vertical depth ruler - the signature graphic of the approved design, and
 * the native twin of apps/web-app/src/components/DepthGauge.jsx.
 *
 * Shows the quoted depth RANGE (never a single number) plus the service
 * area's water-table estimate, which UI/UX doc section 7 makes a required
 * element on every quotation view, not optional decoration.
 *
 * The web version is an SVG. This one is absolutely-positioned Views: same
 * reason as the icons in ui.js - no react-native-svg, so no native module
 * to version-match against the Expo SDK.
 */
import { Text, View } from "react-native";
import { colors } from "../theme";

export default function DepthGauge({
  min,
  max,
  water,
  top = 0,
  bottom,
  height = 260,
  width = 120,
  dark = false,
  labels = true,
}) {
  const lo = Number(min);
  const hi = Number(max);
  const end = bottom || Math.max(600, Math.ceil(((hi || 500) * 1.25) / 100) * 100);
  const pad = 14;
  const y = (v) => pad + ((v - top) / (end - top)) * (height - pad * 2);

  const tickColor = dark ? "#5B6068" : "#B9B6AE";
  const labelColor = dark ? colors.onChromeMuted : colors.muted;
  const markColor = dark ? "#FFFFFF" : colors.chrome;
  const x0 = 40;
  const step = end > 800 ? 50 : 25;

  const ticks = [];
  for (let v = top; v <= end; v += step) ticks.push(v);

  const hasRange = Number.isFinite(lo) && Number.isFinite(hi);
  const waterFt = Number(water);

  return (
    <View style={{ width, height }}>
      {hasRange && (
        <View
          style={{
            position: "absolute",
            left: x0,
            right: 6,
            top: y(lo),
            height: Math.max(4, y(hi) - y(lo)),
            borderRadius: 6,
            backgroundColor: colors.saffron,
            opacity: dark ? 0.92 : 0.85,
          }}
        />
      )}

      {ticks.map((v) => {
        const major = v % 100 === 0;
        const inRange = hasRange && v >= lo && v <= hi;
        return (
          <View key={v} style={{ position: "absolute", left: 0, right: 0, top: y(v) }}>
            <View
              style={{
                position: "absolute",
                left: x0,
                width: major ? 22 : 11,
                height: major ? 1.6 : 1,
                backgroundColor: inRange && !dark ? colors.chrome : tickColor,
              }}
            />
            {major && labels && (
              <View style={{ position: "absolute", left: 0, top: -7, width: x0 - 8, alignItems: "flex-end" }}>
                <Text style={{ fontSize: 11, color: labelColor, fontVariant: ["tabular-nums"] }}>{v}</Text>
              </View>
            )}
          </View>
        );
      })}

      {Number.isFinite(waterFt) && waterFt > top && waterFt < end && (
        <View style={{ position: "absolute", left: x0, right: 6, top: y(waterFt) - 1 }}>
          <Dashes color={markColor} />
          <View
            style={{
              position: "absolute",
              right: -3,
              top: -4,
              width: 10,
              height: 10,
              borderRadius: 5,
              backgroundColor: markColor,
            }}
          />
        </View>
      )}
    </View>
  );
}

/**
 * A dashed rule. borderStyle: "dashed" renders inconsistently between iOS
 * and Android (and ignores the dash length), so the dashes are real Views.
 */
function Dashes({ color }) {
  return (
    <View style={{ flexDirection: "row", overflow: "hidden", height: 2 }}>
      {Array.from({ length: 20 }).map((_, i) => (
        <View key={i} style={{ width: 4, height: 2, marginRight: 3, backgroundColor: color }} />
      ))}
    </View>
  );
}
