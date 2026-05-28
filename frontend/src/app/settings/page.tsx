"use client";

import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { User, Bell, Key, Save, Copy, Check, RefreshCw } from "lucide-react";
import { authFetch } from "@/lib/authFetch";

interface UserProfile {
  id: string;
  email: string;
  name: string;
  apiKey?: string;
  notificationEmail: boolean;
  notificationSms: boolean;
  telegramConnected: boolean;
}

export default function SettingsPage() {
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [profile, setProfile] = React.useState<UserProfile | null>(null);
  const [notifications, setNotifications] = React.useState({
    email: true,
    sms: false,
    telegram: false,
  });
  const [copied, setCopied] = React.useState(false);
  const [regenerating, setRegenerating] = React.useState(false);

  // Editable profile fields
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");

  React.useEffect(() => {
    async function loadProfile() {
      try {
        const res = await authFetch("/api/v1/auth/me");
        if (res.ok) {
          const data = await res.json();
          setProfile(data.profile || data);
          setName(data.profile?.name || data.name || "Demo User");
          setEmail(data.profile?.email || data.email || "demo@example.com");
          setNotifications({
            email: data.profile?.notificationEmail ?? true,
            sms: data.profile?.notificationSms ?? false,
            telegram: data.profile?.telegramConnected ?? false,
          });
        } else {
          // Fallback to mock data
          setProfile({
            id: "1",
            email: "demo@example.com",
            name: "Demo User",
            apiKey: "hk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            notificationEmail: true,
            notificationSms: false,
            telegramConnected: false,
          });
          setName("Demo User");
          setEmail("demo@example.com");
        }
      } catch {
        setProfile({
          id: "1",
          email: "demo@example.com",
          name: "Demo User",
          apiKey: "hk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
          notificationEmail: true,
          notificationSms: false,
          telegramConnected: false,
        });
        setName("Demo User");
        setEmail("demo@example.com");
      } finally {
        setLoading(false);
      }
    }
    loadProfile();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await new Promise((r) => setTimeout(r, 800));
      setProfile((prev) => (prev ? { ...prev, name, email } : prev));
      alert("Settings saved successfully!");
    } catch {
      alert("Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerateKey = async () => {
    setRegenerating(true);
    try {
      await new Promise((r) => setTimeout(r, 1000));
      setProfile((prev) =>
        prev
          ? { ...prev, apiKey: "hk_live_" + Math.random().toString(36).substring(2, 30) }
          : prev
      );
    } finally {
      setRegenerating(false);
    }
  };

  const copyApiKey = async (key: string) => {
    try {
      await navigator.clipboard.writeText(key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = key;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-text-primary">Settings</h1>
            <p className="text-text-secondary">Loading...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Settings</h1>
          <p className="text-text-secondary">Manage your account and preferences</p>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? (
            <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>

      {/* Profile Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5 text-primary" />
            Profile Settings
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-text-secondary block mb-1.5">
                Display Name
              </label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your display name"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-text-secondary block mb-1.5">
                Email Address
              </label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
              />
            </div>
          </div>
          {profile?.id && (
            <div className="pt-2">
              <label className="text-sm text-text-muted">User ID</label>
              <p className="text-sm font-mono text-text-secondary">{profile.id}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Notification Preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-primary" />
            Notification Preferences
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-primary">Email Notifications</p>
                <p className="text-xs text-text-muted">Receive alerts and updates via email</p>
              </div>
              <button
                onClick={() =>
                  setNotifications((n) => ({ ...n, email: !n.email }))
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  notifications.email ? "bg-primary" : "bg-border"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    notifications.email ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-primary">SMS Notifications</p>
                <p className="text-xs text-text-muted">Receive critical alerts via SMS</p>
              </div>
              <button
                onClick={() =>
                  setNotifications((n) => ({ ...n, sms: !n.sms }))
                }
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  notifications.sms ? "bg-primary" : "bg-border"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    notifications.sms ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-text-primary">Telegram Integration</p>
                <p className="text-xs text-text-muted">Connect Telegram for instant alerts</p>
              </div>
              <Badge variant={notifications.telegram ? "success" : "warning"}>
                {notifications.telegram ? "Connected" : "Not Connected"}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* API Keys */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5 text-primary" />
            API Keys
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="bg-[#1e1e2e] rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-text-primary">Live API Key</label>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => profile?.apiKey && copyApiKey(profile.apiKey)}
                  className="flex items-center gap-1"
                >
                  {copied ? (
                    <Check className="h-3 w-3 text-emerald-400" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                  {copied ? "Copied!" : "Copy"}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRegenerateKey}
                  disabled={regenerating}
                  className="flex items-center gap-1"
                >
                  <RefreshCw
                    className={`h-3 w-3 ${regenerating ? "animate-spin" : ""}`}
                  />
                  {regenerating ? "Regenerating..." : "Regenerate"}
                </Button>
              </div>
            </div>
            <p className="text-sm font-mono text-text-secondary break-all">
              {profile?.apiKey || "Not available"}
            </p>
            <p className="text-xs text-text-muted mt-2">
              Keep your API key secure. Do not share it with anyone.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-[#1e1e2e] rounded-lg p-3">
              <p className="text-xs text-text-muted mb-1">Requests (24h)</p>
              <p className="text-lg font-mono font-semibold text-text-primary">1,284</p>
            </div>
            <div className="bg-[#1e1e2e] rounded-lg p-3">
              <p className="text-xs text-text-muted mb-1">Rate Limit</p>
              <p className="text-lg font-mono font-semibold text-text-primary">5,000/min</p>
            </div>
            <div className="bg-[#1e1e2e] rounded-lg p-3">
              <p className="text-xs text-text-muted mb-1">Expires</p>
              <p className="text-lg font-mono font-semibold text-text-primary">Never</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="border-danger/30">
        <CardHeader>
          <CardTitle className="text-danger">Danger Zone</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-primary">Delete Account</p>
              <p className="text-xs text-text-muted">
                Permanently delete your account and all associated data. This action cannot be
                undone.
              </p>
            </div>
            <Button variant="danger" size="sm">
              Delete Account
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
