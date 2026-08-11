import { NextRequest, NextResponse } from "next/server";
export function proxy(request: NextRequest) { if (!request.cookies.has("access_token")) return NextResponse.redirect(new URL("/login", request.url)); return NextResponse.next(); }
export const config = { matcher: ["/admin/:path*", "/staff/:path*"] };
