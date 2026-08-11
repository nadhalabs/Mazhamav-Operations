import "./globals.css";
export const metadata = { title: "Mazha Mav Operations", description: "Operations platform for Mazha Mav" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }

