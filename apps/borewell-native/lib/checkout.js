/**
 * Razorpay checkout - or, on this app, the honest gap where it goes.
 *
 * The backend does the parts that must not be trusted to the client:
 * POST /v1/payments/{id}/create-order creates the order server-side and
 * returns the public key id, and the signed webhook (POST
 * /v1/payments/webhook) is what actually marks a payment completed.
 * Nothing on the client ever decides a payment succeeded.
 *
 * Opening the checkout sheet itself needs either react-native-razorpay or
 * react-native-webview - both native modules, and the registry was
 * unreachable when this was built (see components/ui.js), so neither could
 * be installed and version-checked against Expo SDK 57. Rather than ship a
 * button that crashes on tap, the real order IS created (so the row exists
 * server-side and Razorpay has it) and the screen says plainly that the
 * sheet has to be finished on the web app for now. Because completion only
 * ever arrives via the webhook, the payment then turns "Paid" here on its
 * own - no extra work needed once the sheet is wired up.
 *
 * To finish it: `npx expo install react-native-webview`, then replace the
 * `unsupported` branch below with a WebView loading Razorpay's standard
 * checkout HTML using order.razorpay_key_id and order.razorpay_order_id.
 */
import { DEMO_MODE } from "../services/platform";
import { completeDemoPayment } from "../services/demo";

export async function openCheckout({ order }) {
  if (DEMO_MODE) {
    // Demo mode has no Razorpay account behind it, so the sheet is stubbed
    // and the payment is marked completed the way the signed webhook would.
    await new Promise((resolve) => setTimeout(resolve, 900));
    completeDemoPayment(order.razorpay_order_id);
    return { attempted: true };
  }
  return { attempted: false, unsupported: true, orderId: order.razorpay_order_id };
}
