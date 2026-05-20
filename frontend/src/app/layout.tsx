import "@/app/globals.css";
import { AppShell } from "@/components/layout/AppShell";

export const metadata = {
  title: "Hermes Trading Dashboard",
  description: "Trading Strategy Dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
window.addEventListener('error', function(e) {
  var m = e.message || '';
  var src = e.filename || '';
  if (
    m.includes('MetaMask') ||
    m.includes('chrome-extension://') ||
    src.includes('chrome-extension://') ||
    (m === 'Extension context invalidated.' && src.includes('inpage.js'))
  ) {
    e.stopPropagation();
    e.preventDefault();
  }
}, true);
            `.trim(),
          }}
        />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}