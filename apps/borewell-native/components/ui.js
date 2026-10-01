/**
 * The Field Console UI kit for the native app - the same visual language as
 * apps/web-app/src/components (see docs/adr/0005-field-console-ui.md).
 *
 * Deliberately dependency-free: no icon library, no SVG, no navigation
 * package. Everything here is core react-native, so the app keeps running
 * in Expo Go with no native build and no version-pinning guesswork.
 * Icons are drawn from Views for the same reason - see Icon below.
 */
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { colors, radii } from "../theme";

export function Screen({ children, dark, style, scroll = true, contentStyle }) {
  const background = dark ? colors.chrome : colors.ground;
  if (!scroll) {
    return <View style={[{ flex: 1, backgroundColor: background }, style]}>{children}</View>;
  }
  return (
    <View style={[{ flex: 1, backgroundColor: background }, style]}>
      <ScrollView
        contentContainerStyle={[{ padding: 20, paddingBottom: 120, gap: 14 }, contentStyle]}
        keyboardShouldPersistTaps="handled"
      >
        {children}
      </ScrollView>
    </View>
  );
}

export function Title({ children, size = 30, dark, style }) {
  return (
    <Text style={[{ fontSize: size, fontWeight: "800", letterSpacing: -0.8, color: dark ? "#fff" : colors.ink }, style]}>
      {children}
    </Text>
  );
}

export function Body({ children, muted, dark, size = 15, weight = "400", style, numberOfLines }) {
  const color = muted ? (dark ? colors.onChromeMuted : colors.muted) : dark ? "#fff" : colors.ink;
  return (
    <Text numberOfLines={numberOfLines} style={[{ fontSize: size, fontWeight: weight, color, lineHeight: size * 1.4 }, style]}>
      {children}
    </Text>
  );
}

export function Eyebrow({ children, dark }) {
  // Interpolated children ("Stage {n} of {m}") arrive as an array, and
  // String([...]) would join them with commas.
  const text = (Array.isArray(children) ? children.flat(3).join("") : String(children ?? "")).toUpperCase();
  return (
    <Text style={{ fontSize: 12, letterSpacing: 1.1, fontWeight: "700", color: dark ? colors.onChromeMuted : colors.muted }}>
      {text}
    </Text>
  );
}

export function Amount({ children, size = 28, color = colors.ink, style }) {
  return <Text style={[{ fontSize: size, fontWeight: "800", letterSpacing: -1, color }, style]}>{children}</Text>;
}

export function Card({ children, dark, style, onPress }) {
  const content = (
    <View
      style={[
        { backgroundColor: dark ? colors.chrome : colors.surface, borderRadius: radii.xl, padding: 18, gap: 12 },
        style,
      ]}
    >
      {children}
    </View>
  );
  return onPress ? <Pressable onPress={onPress}>{content}</Pressable> : content;
}

export function Inset({ children, dark, style }) {
  return (
    <View style={[{ backgroundColor: dark ? colors.chrome3 : colors.ground, borderRadius: radii.lg, padding: 14, gap: 8 }, style]}>
      {children}
    </View>
  );
}

export function Row({ children, gap = 10, style, align = "center" }) {
  return <View style={[{ flexDirection: "row", alignItems: align, gap }, style]}>{children}</View>;
}

export function Button({ title, onPress, variant = "dark", disabled, busy, trailing, style, size = "md" }) {
  const palette = {
    dark: { bg: colors.chrome, fg: "#fff", trail: colors.saffron, trailFg: colors.chrome },
    saffron: { bg: colors.saffron, fg: colors.chrome, trail: colors.chrome, trailFg: colors.saffron },
    light: { bg: colors.surface, fg: colors.ink, trail: colors.saffron, trailFg: colors.chrome },
    ghostDark: { bg: colors.chrome3, fg: "#fff", trail: colors.saffron, trailFg: colors.chrome },
  }[variant];
  const height = size === "lg" ? 56 : size === "sm" ? 40 : 50;
  return (
    <Pressable
      onPress={disabled || busy ? undefined : onPress}
      style={({ pressed }) => [
        {
          height,
          borderRadius: 999,
          backgroundColor: palette.bg,
          paddingLeft: 20,
          paddingRight: trailing ? 6 : 20,
          flexDirection: "row",
          alignItems: "center",
          justifyContent: trailing ? "space-between" : "center",
          opacity: disabled ? 0.45 : pressed ? 0.85 : 1,
          gap: 10,
        },
        variant === "light" && { borderWidth: 1, borderColor: colors.line },
        style,
      ]}
    >
      {busy ? (
        <ActivityIndicator color={palette.fg} />
      ) : (
        <Text style={{ color: palette.fg, fontSize: size === "sm" ? 14 : 16, fontWeight: "700" }}>{title}</Text>
      )}
      {trailing && !busy && (
        <View
          style={{
            width: height - 12,
            height: height - 12,
            borderRadius: 999,
            backgroundColor: palette.trail,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Icon name="arrowRight" size={18} color={palette.trailFg} />
        </View>
      )}
    </Pressable>
  );
}

const TONES = {
  neutral: [colors.sunk, colors.ink2],
  saffron: [colors.saffronSoft, colors.saffronInk],
  green: [colors.greenSoft, colors.green],
  red: [colors.redSoft, colors.red],
  slate: [colors.slateSoft, colors.slate],
};

export function Badge({ children, tone = "neutral" }) {
  const [bg, fg] = TONES[tone] || TONES.neutral;
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6, backgroundColor: bg, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 }}>
      <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: fg }} />
      <Text style={{ color: fg, fontSize: 12, fontWeight: "700" }}>{children}</Text>
    </View>
  );
}

export function Pills({ value, onChange, options, dark }) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      style={{ flexGrow: 0 }}
      contentContainerStyle={{ gap: 8, paddingRight: 8 }}
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <Pressable
            key={option.value}
            onPress={() => onChange(option.value)}
            style={{
              height: 38,
              paddingHorizontal: 16,
              borderRadius: 999,
              alignItems: "center",
              justifyContent: "center",
              flexDirection: "row",
              gap: 6,
              backgroundColor: active ? (dark ? colors.saffron : colors.chrome) : dark ? colors.chrome3 : colors.surface,
              borderWidth: !active && !dark ? 1 : 0,
              borderColor: colors.line,
            }}
          >
            <Text style={{ fontWeight: "700", fontSize: 14, color: active ? (dark ? colors.chrome : "#fff") : dark ? "#fff" : colors.ink2 }}>
              {option.label}
            </Text>
            {option.count !== undefined && (
              <Text style={{ fontSize: 12, opacity: 0.7, color: active ? (dark ? colors.chrome : "#fff") : colors.muted }}>{option.count}</Text>
            )}
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

export function Field({ label, hint, error, children }) {
  return (
    <View style={{ gap: 6 }}>
      {label && <Text style={{ fontSize: 13, fontWeight: "700", color: colors.ink2, paddingLeft: 4 }}>{label}</Text>}
      {children}
      {(error || hint) && (
        <Text style={{ fontSize: 13, color: error ? colors.red : colors.muted, paddingLeft: 4 }}>{error || hint}</Text>
      )}
    </View>
  );
}

export function Input(props) {
  return (
    <TextInput
      placeholderTextColor={colors.muted}
      {...props}
      style={[
        {
          height: 52,
          borderRadius: radii.md,
          // Surface, not ground: an input filled with the page colour is
          // invisible on the screens whose background IS ground.
          backgroundColor: colors.surface,
          borderWidth: 1,
          borderColor: colors.line,
          paddingHorizontal: 16,
          fontSize: 16,
          color: colors.ink,
        },
        props.multiline && { height: 96, paddingTop: 14, textAlignVertical: "top" },
        props.style,
      ]}
    />
  );
}

export function Alert({ children, tone = "error", style }) {
  const map = { error: [colors.redSoft, colors.red], info: [colors.saffronSoft, colors.saffronInk], ok: [colors.greenSoft, colors.green] };
  const [bg, fg] = map[tone] || map.error;
  return (
    <View style={[{ backgroundColor: bg, borderRadius: radii.md, padding: 12, flexDirection: "row", gap: 10 }, style]}>
      <Icon name="info" size={18} color={fg} />
      <Text style={{ color: fg, fontSize: 14, fontWeight: "600", flex: 1, lineHeight: 20 }}>{children}</Text>
    </View>
  );
}

export function EmptyState({ title, children, action }) {
  return (
    <View style={{ alignItems: "center", gap: 10, paddingVertical: 32 }}>
      <View style={{ width: 52, height: 52, borderRadius: 26, backgroundColor: colors.ground, alignItems: "center", justifyContent: "center" }}>
        <Icon name="inbox" size={24} color={colors.ink} />
      </View>
      <Text style={{ fontSize: 17, fontWeight: "700" }}>{title}</Text>
      {children && <Body muted style={{ textAlign: "center", maxWidth: 280 }}>{children}</Body>}
      {action}
    </View>
  );
}

export function Loading({ label = "Loading…", dark }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 10, padding: 20 }}>
      <ActivityIndicator color={dark ? "#fff" : colors.ink} />
      <Body muted dark={dark}>{label}</Body>
    </View>
  );
}

export function Sheet({ visible, title, onClose, children, actions }) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: "rgba(20,22,25,0.45)", justifyContent: "flex-end" }}>
        {/* Surface, not ground: insets inside a sheet are ground, and a
            ground-on-ground sheet loses them. */}
        <View style={{ backgroundColor: colors.surface, borderTopLeftRadius: 28, borderTopRightRadius: 28, padding: 20, paddingBottom: 34, maxHeight: "92%", gap: 14 }}>
          <Row>
            <Title size={22}>{title}</Title>
            <View style={{ flex: 1 }} />
            <IconButton name="close" onPress={onClose} />
          </Row>
          <ScrollView contentContainerStyle={{ gap: 14, paddingBottom: 8 }} keyboardShouldPersistTaps="handled">
            {children}
          </ScrollView>
          {actions}
        </View>
      </View>
    </Modal>
  );
}

export function Confirm({ visible, title, body, confirmLabel, onConfirm, onClose, busy }) {
  return (
    <Sheet
      visible={visible}
      title={title}
      onClose={onClose}
      actions={
        <Row gap={10}>
          <Button title="Cancel" variant="light" onPress={onClose} style={{ flex: 1 }} />
          <Button title={confirmLabel} onPress={onConfirm} busy={busy} style={{ flex: 1.4 }} />
        </Row>
      }
    >
      <Body muted>{body}</Body>
    </Sheet>
  );
}

export function Toast({ message }) {
  if (!message) return null;
  return (
    <View style={{ pointerEvents: "none", position: "absolute", left: 20, right: 20, bottom: 104, alignItems: "center" }}>
      <View style={{ backgroundColor: colors.chrome, borderRadius: 999, paddingHorizontal: 20, paddingVertical: 12, flexDirection: "row", alignItems: "center", gap: 10 }}>
        <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: colors.saffron }} />
        <Text style={{ color: "#fff", fontWeight: "700" }}>{message}</Text>
      </View>
    </View>
  );
}

export function KeyValue({ k, v, dark }) {
  return (
    <View style={{ gap: 2 }}>
      <Body size={13} muted dark={dark}>{k}</Body>
      <Body size={16} weight="700" dark={dark}>{v}</Body>
    </View>
  );
}

export function Avatar({ initials, size = 42, tone = "saffron" }) {
  const bg = tone === "saffron" ? colors.saffron : colors.sunk;
  const fg = tone === "saffron" ? colors.chrome : colors.ink2;
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: bg, alignItems: "center", justifyContent: "center" }}>
      <Text style={{ color: fg, fontWeight: "800", fontSize: size * 0.36 }}>{initials}</Text>
    </View>
  );
}

export function Tile({ children, tone = "ground", size = 44 }) {
  return (
    <View
      style={{
        width: size,
        height: size,
        borderRadius: 14,
        backgroundColor: tone === "saffron" ? colors.saffron : tone === "dark" ? colors.chrome3 : colors.ground,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {children}
    </View>
  );
}

export function ListRow({ children, onPress, active, style }) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        {
          flexDirection: "row",
          alignItems: "center",
          gap: 12,
          padding: 12,
          borderRadius: radii.lg,
          backgroundColor: active ? colors.chrome : "transparent",
          opacity: pressed ? 0.85 : 1,
        },
        style,
      ]}
    >
      {children}
    </Pressable>
  );
}

export function IconButton({ name, onPress, dark, dot, size = 44 }) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        width: size,
        height: size,
        borderRadius: size / 2,
        backgroundColor: dark ? colors.chrome3 : colors.surface,
        borderWidth: dark ? 0 : 1,
        borderColor: colors.line,
        alignItems: "center",
        justifyContent: "center",
        opacity: pressed ? 0.7 : 1,
      })}
    >
      <Icon name={name} size={20} color={dark ? "#fff" : colors.ink} />
      {dot && (
        <View style={{ position: "absolute", top: 9, right: 10, width: 8, height: 8, borderRadius: 4, backgroundColor: colors.saffron }} />
      )}
    </Pressable>
  );
}

/**
 * Icons drawn with Views.
 *
 * react-native-svg would be the obvious choice, but it is a native module
 * whose version has to match the Expo SDK exactly, and the version-check
 * API was unreachable when this was built. Rather than guess a version and
 * hand over an app that may not bundle, these are geometric shapes from
 * core primitives - no dependency, no native build, works in Expo Go.
 * Swap in a real icon set when someone can run `npx expo install
 * react-native-svg` against the live registry.
 */
export function Icon({ name, size = 20, color = colors.ink }) {
  const s = size;
  const bar = (w, h, extra) => ({ position: "absolute", width: w, height: h, backgroundColor: color, borderRadius: Math.min(w, h) / 2, ...extra });
  const wrap = { width: s, height: s, alignItems: "center", justifyContent: "center" };

  switch (name) {
    case "chevronRight":
    case "chevronLeft":
    case "arrowRight":
      return (
        <View style={wrap}>
          {name === "arrowRight" && <View style={bar(s * 0.62, 2, { left: s * 0.1 })} />}
          <View
            style={{
              width: s * 0.34,
              height: s * 0.34,
              borderTopWidth: 2,
              borderRightWidth: 2,
              borderColor: color,
              transform: [{ rotate: name === "chevronLeft" ? "225deg" : "45deg" }],
              marginLeft: name === "chevronLeft" ? s * 0.08 : name === "arrowRight" ? s * 0.28 : 0,
            }}
          />
        </View>
      );
    case "chevronDown":
      return (
        <View style={wrap}>
          <View style={{ width: s * 0.34, height: s * 0.34, borderTopWidth: 2, borderRightWidth: 2, borderColor: color, transform: [{ rotate: "135deg" }], marginBottom: s * 0.1 }} />
        </View>
      );
    case "check":
      return (
        <View style={wrap}>
          <View
            style={{
              width: s * 0.3,
              height: s * 0.6,
              borderBottomWidth: 2.4,
              borderRightWidth: 2.4,
              borderColor: color,
              transform: [{ rotate: "45deg" }],
              marginTop: -s * 0.1,
            }}
          />
        </View>
      );
    case "close":
      return (
        <View style={wrap}>
          <View style={bar(s * 0.7, 2, { transform: [{ rotate: "45deg" }] })} />
          <View style={bar(s * 0.7, 2, { transform: [{ rotate: "-45deg" }] })} />
        </View>
      );
    case "plus":
      return (
        <View style={wrap}>
          <View style={bar(s * 0.7, 2.2, {})} />
          <View style={bar(2.2, s * 0.7, {})} />
        </View>
      );
    case "search":
      return (
        <View style={wrap}>
          <View style={{ width: s * 0.55, height: s * 0.55, borderRadius: s * 0.3, borderWidth: 2, borderColor: color, marginTop: -s * 0.08, marginLeft: -s * 0.08 }} />
          <View style={bar(s * 0.28, 2, { transform: [{ rotate: "45deg" }], right: s * 0.08, bottom: s * 0.16 })} />
        </View>
      );
    case "pin":
      return (
        <View style={wrap}>
          <View style={{ width: s * 0.55, height: s * 0.55, borderRadius: s * 0.3, borderWidth: 2, borderColor: color, marginTop: -s * 0.12 }} />
          <View style={{ position: "absolute", bottom: s * 0.08, width: 0, height: 0, borderLeftWidth: s * 0.14, borderRightWidth: s * 0.14, borderTopWidth: s * 0.22, borderLeftColor: "transparent", borderRightColor: "transparent", borderTopColor: color }} />
        </View>
      );
    case "truck":
      return (
        <View style={wrap}>
          <View style={{ position: "absolute", left: s * 0.04, top: s * 0.28, width: s * 0.48, height: s * 0.32, borderRadius: 2, backgroundColor: color }} />
          <View style={{ position: "absolute", left: s * 0.56, top: s * 0.38, width: s * 0.36, height: s * 0.22, borderRadius: 2, borderTopRightRadius: 5, backgroundColor: color }} />
          <View style={{ position: "absolute", left: s * 0.14, bottom: s * 0.12, width: s * 0.15, height: s * 0.15, borderRadius: s * 0.075, backgroundColor: color }} />
          <View style={{ position: "absolute", right: s * 0.14, bottom: s * 0.12, width: s * 0.15, height: s * 0.15, borderRadius: s * 0.075, backgroundColor: color }} />
        </View>
      );
    case "drop":
      // A square with three round corners and one sharp one, rotated so the
      // sharp corner points up: a water drop. Filled rather than outlined -
      // a 2px outline at 16-20px closes up into a ring.
      return (
        <View style={wrap}>
          <View
            style={{
              width: s * 0.52,
              height: s * 0.52,
              backgroundColor: color,
              borderTopLeftRadius: s * 0.26,
              borderBottomLeftRadius: s * 0.26,
              borderBottomRightRadius: s * 0.26,
              borderTopRightRadius: 1,
              // Sharp corner sits at top-right, i.e. 45 deg clockwise from
              // straight up; -45 deg puts the point at the top.
              transform: [{ rotate: "-45deg" }],
            }}
          />
        </View>
      );
    case "clock":
      return (
        <View style={wrap}>
          <View style={{ width: s * 0.72, height: s * 0.72, borderRadius: s * 0.36, borderWidth: 2, borderColor: color }} />
          <View style={bar(2, s * 0.2, { top: s * 0.26 })} />
          <View style={bar(s * 0.18, 2, { left: s * 0.5, top: s * 0.46 })} />
        </View>
      );
    case "inbox":
      return (
        <View style={wrap}>
          <View style={{ width: s * 0.78, height: s * 0.6, borderWidth: 2, borderColor: color, borderRadius: 4 }} />
          <View style={bar(s * 0.34, 2, { top: s * 0.5 })} />
        </View>
      );
    case "user":
      return (
        <View style={wrap}>
          <View style={{ width: s * 0.36, height: s * 0.36, borderRadius: s * 0.18, borderWidth: 2, borderColor: color, marginTop: -s * 0.16 }} />
          <View style={{ position: "absolute", bottom: s * 0.1, width: s * 0.66, height: s * 0.3, borderTopLeftRadius: s * 0.33, borderTopRightRadius: s * 0.33, borderWidth: 2, borderBottomWidth: 0, borderColor: color }} />
        </View>
      );
    case "logout":
      return (
        <View style={wrap}>
          <View style={{ position: "absolute", left: s * 0.1, width: s * 0.34, height: s * 0.72, borderWidth: 2, borderRightWidth: 0, borderColor: color, borderRadius: 3 }} />
          <View style={bar(s * 0.4, 2, { right: s * 0.06 })} />
          <View style={{ position: "absolute", right: s * 0.06, width: s * 0.22, height: s * 0.22, borderTopWidth: 2, borderRightWidth: 2, borderColor: color, transform: [{ rotate: "45deg" }] }} />
        </View>
      );
    case "bell":
      return (
        <View style={wrap}>
          <View style={{ width: s * 0.56, height: s * 0.5, borderWidth: 2, borderColor: color, borderTopLeftRadius: s * 0.28, borderTopRightRadius: s * 0.28, marginBottom: s * 0.12 }} />
          <View style={bar(s * 0.7, 2, { bottom: s * 0.24 })} />
          <View style={bar(s * 0.16, 2, { bottom: s * 0.14 })} />
        </View>
      );
    case "wallet":
      return (
        <View style={wrap}>
          <View style={{ width: s * 0.78, height: s * 0.58, borderWidth: 2, borderColor: color, borderRadius: 4 }} />
          <View style={bar(s * 0.16, 4, { right: s * 0.14, top: s * 0.46 })} />
        </View>
      );
    case "board":
      return (
        <View style={wrap}>
          <View style={{ flexDirection: "row", gap: 3, alignItems: "flex-start" }}>
            <View style={{ width: s * 0.16, height: s * 0.62, borderWidth: 2, borderColor: color, borderRadius: 2 }} />
            <View style={{ width: s * 0.16, height: s * 0.44, borderWidth: 2, borderColor: color, borderRadius: 2 }} />
            <View style={{ width: s * 0.16, height: s * 0.3, borderWidth: 2, borderColor: color, borderRadius: 2 }} />
          </View>
        </View>
      );
    case "sliders":
      return (
        <View style={wrap}>
          <View style={bar(s * 0.72, 2, { top: s * 0.26 })} />
          <View style={bar(s * 0.72, 2, { bottom: s * 0.26 })} />
          <View style={{ position: "absolute", top: s * 0.18, left: s * 0.52, width: s * 0.18, height: s * 0.18, borderRadius: s * 0.09, backgroundColor: color }} />
          <View style={{ position: "absolute", bottom: s * 0.18, left: s * 0.22, width: s * 0.18, height: s * 0.18, borderRadius: s * 0.09, backgroundColor: color }} />
        </View>
      );
    case "home":
      return (
        <View style={wrap}>
          <View style={{ width: s * 0.5, height: s * 0.5, borderWidth: 2, borderColor: color, transform: [{ rotate: "45deg" }], borderBottomWidth: 0, borderRightWidth: 0, marginTop: -s * 0.2, borderTopLeftRadius: 4 }} />
          <View style={{ position: "absolute", bottom: s * 0.14, width: s * 0.56, height: s * 0.34, borderWidth: 2, borderTopWidth: 0, borderColor: color }} />
        </View>
      );
    case "briefcase":
      return (
        <View style={wrap}>
          <View style={{ width: s * 0.78, height: s * 0.54, borderWidth: 2, borderColor: color, borderRadius: 4, marginTop: s * 0.08 }} />
          <View style={{ position: "absolute", top: s * 0.14, width: s * 0.32, height: s * 0.14, borderWidth: 2, borderBottomWidth: 0, borderColor: color, borderTopLeftRadius: 3, borderTopRightRadius: 3 }} />
        </View>
      );
    case "info":
    default:
      return (
        <View style={wrap}>
          <View style={{ width: s * 0.78, height: s * 0.78, borderRadius: s * 0.39, borderWidth: 2, borderColor: color }} />
          <View style={bar(2, s * 0.26, { top: s * 0.36 })} />
          <View style={bar(2, 2, { top: s * 0.24 })} />
        </View>
      );
  }
}

/** The three job types share one icon vocabulary across every screen. */
export function JobTypeIcon({ jobType, size = 20, color }) {
  const name = jobType === "residential" ? "home" : jobType === "commercial" ? "briefcase" : "drop";
  return <Icon name={name} size={size} color={color} />;
}

export function Logo({ size = 34 }) {
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: colors.saffron, alignItems: "center", justifyContent: "center" }}>
      <View style={{ width: 2.6, height: size * 0.42, backgroundColor: colors.chrome, borderRadius: 2, marginTop: -size * 0.06 }} />
      <View style={{ position: "absolute", top: size * 0.34, width: size * 0.5, height: 2.2, backgroundColor: colors.chrome, borderRadius: 2 }} />
      <View
        style={{
          position: "absolute",
          bottom: size * 0.16,
          width: 0,
          height: 0,
          borderLeftWidth: size * 0.1,
          borderRightWidth: size * 0.1,
          borderTopWidth: size * 0.16,
          borderLeftColor: "transparent",
          borderRightColor: "transparent",
          borderTopColor: colors.chrome,
        }}
      />
    </View>
  );
}

export const shadow = StyleSheet.create({
  pop: {
    shadowColor: "#141619",
    shadowOpacity: 0.18,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 12 },
    elevation: 8,
  },
});
