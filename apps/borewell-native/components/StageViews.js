/**
 * The two ways a job's progress is shown, ported from
 * apps/web-app/src/components/StageViews.jsx.
 *
 * StageRail   - the full 14-stage rail platform-spine's state machine
 *               enforces, for the contractor.
 * CustomerSteps - the same 14 stages collapsed into the 5 a customer cares
 *               about. Both read their labels from theme.js; no screen
 *               re-labels a stage itself.
 */
import { Text, View } from "react-native";
import {
  CUSTOMER_STEPS,
  JOB_STAGES,
  STAGE_LABELS,
  colors,
  customerStepIndex,
  stageIndex,
} from "../theme";
import { Icon } from "./ui";

export function StageRail({ status, dark }) {
  const current = stageIndex(status);
  return (
    <View style={{ gap: 0 }}>
      {JOB_STAGES.map((stage, i) => {
        const done = i < current;
        const now = i === current;
        return (
          <View key={stage}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
              <View
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: 10,
                  alignItems: "center",
                  justifyContent: "center",
                  backgroundColor: done ? colors.chrome : now ? colors.saffron : "transparent",
                  borderWidth: done || now ? 0 : 2,
                  borderColor: dark ? colors.chrome3 : colors.line,
                }}
              >
                {done && <Icon name="check" size={12} color="#fff" />}
                {now && <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: colors.chrome }} />}
              </View>
              <Text
                style={{
                  fontSize: 15,
                  fontWeight: now ? "700" : "500",
                  color: now
                    ? dark ? "#fff" : colors.ink
                    : done
                      ? dark ? colors.onChromeMuted : colors.ink2
                      : dark ? "#5B6068" : colors.muted,
                }}
              >
                {STAGE_LABELS[stage]}
              </Text>
            </View>
            {i < JOB_STAGES.length - 1 && (
              <View
                style={{
                  width: 2,
                  height: 14,
                  marginLeft: 9,
                  backgroundColor: i < current ? colors.chrome : dark ? colors.chrome3 : colors.line,
                }}
              />
            )}
          </View>
        );
      })}
    </View>
  );
}

export function CustomerSteps({ status, dark }) {
  const current = customerStepIndex(status);
  return (
    <View style={{ flexDirection: "row", gap: 6 }}>
      {CUSTOMER_STEPS.map((step, i) => {
        const done = i < current;
        const now = i === current;
        return (
          <View key={step.label} style={{ flex: 1, gap: 6 }}>
            <View
              style={{
                height: 4,
                borderRadius: 2,
                backgroundColor: done
                  ? colors.chrome
                  : now
                    ? colors.saffron
                    : dark ? colors.chrome3 : colors.line,
              }}
            />
            <Text
              numberOfLines={1}
              style={{
                fontSize: 10.5,
                fontWeight: now ? "700" : "500",
                color: now
                  ? dark ? "#fff" : colors.ink
                  : dark ? colors.onChromeMuted : colors.muted,
              }}
            >
              {step.label}
            </Text>
          </View>
        );
      })}
    </View>
  );
}
