/**
 * Razorpay Checkout in a full-screen WebView (react-native-webview).
 *
 * onResult receives one of:
 *   { status: "success", result: { razorpay_order_id, razorpay_payment_id, razorpay_signature } }
 *   { status: "dismissed" }            - the customer closed it
 *   { status: "failed", message }      - Razorpay or the network reported a failure
 * "success" is only a claim until the server verifies the signature.
 */
import { Linking, Modal, Pressable, Text, View } from "react-native";
import { WebView } from "react-native-webview";
import { colors } from "../theme";
import { checkoutHtml, checkoutOptions } from "../lib/razorpay";
import { TOP_INSET } from "./AppShell";

// Banks and UPI apps are opened through custom schemes (upi:, intent:, gpay:,
// phonepe: ...). A WebView cannot load those, so hand them to Android.
const isWebUrl = (url) => /^(https?|about|data|blob):/i.test(url);

export default function RazorpaySheet({ order, email, onResult }) {
  if (!order) return null;
  const html = checkoutHtml(checkoutOptions({ order, email }));

  function onMessage(event) {
    let message;
    try {
      message = JSON.parse(event.nativeEvent.data);
    } catch {
      return;
    }
    if (message.type === "success") onResult({ status: "success", result: message.result });
    else if (message.type === "dismissed") onResult({ status: "dismissed" });
    else onResult({ status: "failed", message: message.message || "The payment failed." });
  }

  return (
    <Modal visible animationType="slide" onRequestClose={() => onResult({ status: "dismissed" })}>
      <View style={{ flex: 1, backgroundColor: colors.chrome }}>
        <View style={{ paddingTop: TOP_INSET, paddingHorizontal: 16, paddingBottom: 10, flexDirection: "row", alignItems: "center" }}>
          <Text style={{ color: "#fff", fontWeight: "800", fontSize: 16, flex: 1 }}>Secure payment</Text>
          <Pressable onPress={() => onResult({ status: "dismissed" })} hitSlop={12}>
            <Text style={{ color: colors.saffron, fontWeight: "700", fontSize: 15 }}>Cancel</Text>
          </Pressable>
        </View>
        <WebView
          style={{ flex: 1 }}
          originWhitelist={["*"]}
          source={{ html, baseUrl: "https://checkout.razorpay.com" }}
          onMessage={onMessage}
          javaScriptEnabled
          domStorageEnabled
          setSupportMultipleWindows={false}
          onShouldStartLoadWithRequest={(request) => {
            if (isWebUrl(request.url)) return true;
            Linking.openURL(request.url).catch(() => {});
            return false;
          }}
          onError={() => onResult({ status: "failed", message: "Could not load the payment page. Check your internet connection." })}
        />
      </View>
    </Modal>
  );
}
