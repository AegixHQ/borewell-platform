/**
 * Google sign-in on Android/iOS, using @react-native-google-signin (the
 * library Expo's current Google-authentication guide recommends over a
 * browser redirect). It hands back a Google ID token; platform-spine
 * verifies it (POST /v1/auth/google) and issues OUR session token - nothing
 * Google returns is trusted by the app itself.
 *
 * EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID is the *Web application* OAuth client ID.
 * It is what the ID token's audience is set to, so the same value must be in
 * the server's GOOGLE_CLIENT_IDS. The Android client (package + SHA-1) must
 * also exist in the same Google Cloud project - Google uses it to recognise
 * the app - but its ID is never put in code. Not available in Expo Go (it is
 * a native module); see lib/google.web.js for the web preview.
 */
import { GoogleSignin, isErrorWithCode, statusCodes } from "@react-native-google-signin/google-signin";

const WEB_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;

export const GOOGLE_ENABLED = !!WEB_CLIENT_ID;

let configured = false;

/** Opens Google's account picker. Resolves to { idToken, email }, or null if the
 * person backed out. Throws an Error with a readable message otherwise. */
export async function getGoogleIdToken() {
  if (!configured) {
    GoogleSignin.configure({ webClientId: WEB_CLIENT_ID });
    configured = true;
  }
  try {
    await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });
    // Forget the cached account so the picker always shows - otherwise a
    // second person on the same phone would be signed in as the first.
    await GoogleSignin.signOut().catch(() => {});
    const response = await GoogleSignin.signIn();
    if (response.type !== "success") return null;
    if (!response.data.idToken) throw new Error("Google did not return a sign-in token.");
    return { idToken: response.data.idToken, email: response.data.user.email };
  } catch (err) {
    if (isErrorWithCode(err)) {
      if (err.code === statusCodes.SIGN_IN_CANCELLED) return null;
      if (err.code === statusCodes.PLAY_SERVICES_NOT_AVAILABLE) {
        throw new Error("Google Play services are missing or out of date on this phone.");
      }
      if (err.code === statusCodes.IN_PROGRESS) return null;
    }
    throw new Error(
      "Google sign-in could not start. If this keeps happening, the app's Google setup (client ID or signing fingerprint) is probably wrong."
    );
  }
}
