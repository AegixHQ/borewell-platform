/**
 * The route table: which component each route name renders, and which tabs
 * each role gets. Client-side role routing is PRESENTATION ONLY and never
 * the security boundary - that is every service's require_role() (ADR-0002,
 * same note as apps/web-app/src/App.jsx).
 */
import Account from "./Account";
import CustomerHome from "./customer/CustomerHome";
import NewRequest from "./customer/NewRequest";
import CustomerJob from "./customer/CustomerJob";
import ContractorBoard from "./contractor/ContractorBoard";
import ContractorJob from "./contractor/ContractorJob";
import FindRigs from "./contractor/FindRigs";
import Bookings from "./contractor/Bookings";
import Setup from "./contractor/Setup";
import OwnerRequests from "./owner/OwnerRequests";
import OwnerFleet from "./owner/OwnerFleet";

export const SCREENS = {
  "customer.home": { component: CustomerHome, title: "Your borewells" },
  "customer.new": { component: NewRequest, title: "New request" },
  "customer.job": { component: CustomerJob, title: "Your borewell" },

  "contractor.board": { component: ContractorBoard, title: "Board" },
  "contractor.job": { component: ContractorJob, title: "Job" },
  "contractor.rigs": { component: FindRigs, title: "Find rigs" },
  "contractor.bookings": { component: Bookings, title: "Bookings" },
  "contractor.setup": { component: Setup, title: "Setup" },

  "owner.requests": { component: OwnerRequests, title: "Requests" },
  "owner.fleet": { component: OwnerFleet, title: "Fleet" },

  account: { component: Account, title: "Account" },
};

const CUSTOMER_TABS = [
  { route: "customer.home", label: "Jobs", icon: "drop" },
  { route: "customer.new", label: "Request", icon: "plus" },
  { route: "account", label: "You", icon: "user" },
];

const CONTRACTOR_TABS = [
  { route: "contractor.board", label: "Board", icon: "board" },
  { route: "contractor.rigs", label: "Rigs", icon: "search" },
  { route: "contractor.bookings", label: "Bookings", icon: "truck" },
  { route: "contractor.setup", label: "Setup", icon: "sliders" },
  { route: "account", label: "You", icon: "user" },
];

const OWNER_TABS = [
  { route: "owner.requests", label: "Requests", icon: "inbox" },
  { route: "owner.fleet", label: "Fleet", icon: "truck" },
  { route: "account", label: "You", icon: "user" },
];

export const TABS_FOR_ROLE = {
  customer: CUSTOMER_TABS,
  contractor: CONTRACTOR_TABS,
  // No dedicated admin workspace exists yet - admins see the contractor
  // one, the same fallback the web app makes.
  admin: CONTRACTOR_TABS,
  resource_owner: OWNER_TABS,
};

export function homeFor(role) {
  return (TABS_FOR_ROLE[role] || CUSTOMER_TABS)[0].route;
}

/** Which tab stays lit while a pushed screen (a job, a search) is open. */
export const TAB_FOR_ROUTE = {
  "customer.job": "customer.home",
  "contractor.job": "contractor.board",
};
