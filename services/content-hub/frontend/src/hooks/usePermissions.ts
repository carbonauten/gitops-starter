import { useMemo } from "react";

import { canApproveCertificates, canApproveContent, canEditContent, canManageUsers, type User } from "../api/client";
import { useAuth } from "./useAuth";

export function usePermissions() {
  const { user } = useAuth();

  return useMemo(
    () => ({
      user,
      canEdit: user ? canEditContent(user.role) : false,
      canManageUsers: user ? canManageUsers(user.role) : false,
      canApprove: user ? canApproveContent(user.role) : false,
      canApproveCertificates: user ? canApproveCertificates(user.role) : false,
      isViewer: user?.role === "viewer",
      isItMaster: user?.role === "it_master",
      isCertManager: user?.role === "certificate_manager",
    }),
    [user],
  );
}
