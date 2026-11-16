/**
 * Razorpay Checkout, shared pieces. The sheet itself is
 * components/RazorpaySheet.js (native WebView) and RazorpaySheet.web.js
 * (checkout.js straight into the page).
 *
 * The app never decides a payment succeeded. Checkout hands back an order
 * id, payment id and signature; POST /v1/payments/{id}/verify checks that
 * signature with the key secret, which only the server has.
 */
import { colors } from "../theme";

/** The options object Checkout takes, built from POST .../create-order. */
export function checkoutOptions({ order, email }) {
  return {
    key: order.razorpay_key_id,
    order_id: order.razorpay_order_id,
    amount: order.amount_paise,
    currency: order.currency || "INR",
    name: "Borewell",
    description: "Borewell job payment",
    prefill: email ? { email } : undefined,
    theme: { color: colors.saffron },
  };
}

/** The page the native WebView loads. Options are embedded as JSON with "<"
 * escaped, so nothing in an email address can close the script tag. */
export function checkoutHtml(options) {
  const json = JSON.stringify(options).replace(/</g, "\\u003c");
  return `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{margin:0;background:#141619;color:#fff;font:15px sans-serif;display:flex;align-items:center;justify-content:center;height:100vh}</style>
</head><body><p>Opening secure checkout…</p>
<script src="https://checkout.razorpay.com/v1/checkout.js"></script>
<script>
function send(o){window.ReactNativeWebView.postMessage(JSON.stringify(o));}
window.addEventListener("load",function(){
  if(!window.Razorpay){send({type:"error",message:"Could not load Razorpay. Check your internet connection."});return;}
  var o=${json};
  o.handler=function(r){send({type:"success",result:r});};
  o.modal={ondismiss:function(){send({type:"dismissed"});}};
  var rzp=new Razorpay(o);
  rzp.on("payment.failed",function(r){send({type:"failed",message:(r&&r.error&&r.error.description)||"The payment failed."});});
  rzp.open();
});
</script></body></html>`;
}
