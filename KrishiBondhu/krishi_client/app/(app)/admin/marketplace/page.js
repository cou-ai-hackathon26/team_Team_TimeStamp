import { PrivateAccess } from "@/components/auth/PrivateAccess.js";
import MarketplaceReview from "@/components/marketplace/MarketplaceReview.js";

export default function AdminMarketplacePage() {
  return <PrivateAccess><MarketplaceReview /></PrivateAccess>;
}
