export interface ClientYear {
  year: string;
  itrType: string;
  status: string;
}

export interface ClientRecord {
  /** Legacy internal database ID. Use only in temporary compatibility adapters. */
  id: number;
  /** Stable opaque ID used by routes and resource APIs. */
  publicId: string;
  pan: string;
  name: string;
  /** CBDT three-part name.  Backend derives the full ``name`` from these. */
  firstName?: string;
  middleName?: string;
  surname?: string;
  email?: string | null;
  mobile?: string | null;
  aadhaar?: string | null;
  dob?: string | null;
  archived: boolean;
  archivedAt?: string | null;
  years: ClientYear[];
  createdAt: string;
  updatedAt: string;
}

export interface ClientListParams {
  search?: string;
  assessmentYear?: string;
  status?: string;
  include_archived?: boolean;
}

export interface ClientUpsertPayload {
  pan: string;
  /** Full name; derived from parts when firstName/middleName/surname are used. */
  name?: string;
  firstName?: string;
  middleName?: string;
  surname?: string;
  email?: string;
  mobile?: string;
  aadhaar?: string;
  dob?: string;
  portal_password?: string;
}
