/**
 * The frame every screen sits in: a top bar (brand, or a back button when
 * the stack is deeper than one), and the role's tab bar at the bottom.
 * Native counterpart of apps/web-app/src/components/AppShell.jsx, where the
 * same thing is a sticky pill nav.
 */
import { Platform, Pressable, StatusBar, Text, View } from "react-native";
import { colors } from "../theme";
import { useNav } from "../lib/nav";
import { useSession } from "../lib/session";
import { DEMO_MODE } from "../services/platform";
import { Body, Eyebrow, Icon, IconButton, Logo, Title } from "./ui";

// There is no safe-area library here (react-native-safe-area-context is a
// native module - see lib/nav.js for the same call), so the notch is
// handled with the one number that actually matters: the status bar.
export const TOP_INSET = Platform.OS === "ios" ? 52 : (StatusBar.currentHeight || 24) + 8;
export const BOTTOM_INSET = Platform.OS === "ios" ? 26 : 12;

export function TopBar({ title, onSignOut }) {
  const { depth, goBack } = useNav();
  const { session } = useSession();

  return (
    <View
      style={{
        paddingTop: TOP_INSET,
        paddingHorizontal: 20,
        paddingBottom: 10,
        flexDirection: "row",
        alignItems: "center",
        gap: 12,
        backgroundColor: colors.ground,
      }}
    >
      {depth > 1 ? (
        <IconButton name="chevronLeft" onPress={goBack} size={40} />
      ) : (
        <Logo size={34} />
      )}
      <View style={{ flex: 1, minWidth: 0, paddingRight: 4 }}>
        <Text numberOfLines={1} style={{ fontSize: 17, fontWeight: "800", letterSpacing: -0.4, color: colors.ink }}>
          {title}
        </Text>
        {!!session && (
          <Text numberOfLines={1} style={{ fontSize: 12, color: colors.muted }}>
            {session.email}
          </Text>
        )}
      </View>
      {DEMO_MODE && (
        <View style={{ backgroundColor: colors.saffron, borderRadius: 999, paddingHorizontal: 9, paddingVertical: 4 }}>
          <Text style={{ fontSize: 10, fontWeight: "800", letterSpacing: 0.8, color: colors.chrome }}>DEMO</Text>
        </View>
      )}
      {onSignOut && <IconButton name="logout" onPress={onSignOut} size={40} />}
    </View>
  );
}

/** The heading block at the top of a screen's scroll area. */
export function PageHeader({ eyebrow, title, subtitle, right }) {
  return (
    <View style={{ gap: 6, paddingTop: 4, paddingBottom: 2 }}>
      {!!eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 12 }}>
        <View style={{ flex: 1 }}>
          <Title size={28}>{title}</Title>
        </View>
        {right}
      </View>
      {!!subtitle && <Body muted>{subtitle}</Body>}
    </View>
  );
}

export function TabBar({ tabs, current, onSelect }) {
  return (
    <View
      style={{
        position: "absolute",
        left: 14,
        right: 14,
        bottom: BOTTOM_INSET,
        height: 64,
        borderRadius: 32,
        backgroundColor: colors.chrome,
        flexDirection: "row",
        alignItems: "center",
        paddingHorizontal: 8,
      }}
    >
      {tabs.map((tab) => {
        const active = tab.route === current;
        return (
          <Pressable
            key={tab.route}
            onPress={() => onSelect(tab)}
            style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: 3, height: 48 }}
          >
            <View
              style={{
                width: 38,
                height: 30,
                borderRadius: 15,
                alignItems: "center",
                justifyContent: "center",
                backgroundColor: active ? colors.saffron : "transparent",
              }}
            >
              <Icon name={tab.icon} size={19} color={active ? colors.chrome : "#8D9299"} />
              {tab.badge > 0 && (
                <View
                  style={{
                    position: "absolute",
                    top: 1,
                    right: 4,
                    minWidth: 14,
                    height: 14,
                    borderRadius: 7,
                    paddingHorizontal: 3,
                    backgroundColor: active ? colors.chrome : colors.saffron,
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Text style={{ fontSize: 9, fontWeight: "800", color: active ? colors.saffron : colors.chrome }}>
                    {tab.badge > 9 ? "9+" : tab.badge}
                  </Text>
                </View>
              )}
            </View>
            <Text style={{ fontSize: 10.5, fontWeight: "700", color: active ? "#fff" : "#8D9299" }}>{tab.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}
