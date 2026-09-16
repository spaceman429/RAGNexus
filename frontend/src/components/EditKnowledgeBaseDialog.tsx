import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { fetchDetail, updateKnowledgeBase } from "@/services/knowledgeBaseService";
import type { KnowledgeBaseTreeItem, UpdateKnowledgeBaseRequest } from "@/types/api";

interface EditKnowledgeBaseDialogProps {
  kb: KnowledgeBaseTreeItem | null;
  onClose: () => void;
  onSaved: () => void;
}

export function EditKnowledgeBaseDialog({ kb, onClose, onSaved }: EditKnowledgeBaseDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [settingsText, setSettingsText] = useState("{}");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!kb) {
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchDetail(kb.kb_id)
      .then((detail) => {
        if (cancelled) {
          return;
        }
        setName(detail.name);
        setDescription(detail.description ?? "");
        setSettingsText(JSON.stringify(detail.settings ?? {}, null, 2));
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [kb]);

  if (!kb) {
    return null;
  }

  const kbId = kb.kb_id;

  async function handleSave() {
    setError(null);
    let settings: Record<string, unknown> | undefined;
    try {
      settings = JSON.parse(settingsText) as Record<string, unknown>;
      if (typeof settings !== "object" || settings === null || Array.isArray(settings)) {
        throw new Error("settings 必须是 JSON 对象");
      }
    } catch (parseError) {
      setError(parseError instanceof Error ? parseError.message : "settings JSON 格式错误");
      return;
    }

    const payload: UpdateKnowledgeBaseRequest = {
      name: name.trim(),
      description: description.trim() || undefined,
      settings,
    };

    setSaving(true);
    try {
      await updateKnowledgeBase(kbId, payload);
      onSaved();
      onClose();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="flex max-h-[90vh] w-full max-w-2xl flex-col shadow-lg">
        <CardHeader>
          <CardTitle className="text-lg">编辑知识库</CardTitle>
        </CardHeader>
        <CardContent className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-10 text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              加载中...
            </div>
          ) : (
            <>
              <div className="space-y-2">
                <Label htmlFor="edit-kb-name">名称</Label>
                <Input id="edit-kb-name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-kb-description">描述</Label>
                <Textarea
                  id="edit-kb-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-kb-settings">settings（JSON）</Label>
                <Textarea
                  id="edit-kb-settings"
                  className="min-h-[220px] font-mono text-xs"
                  value={settingsText}
                  onChange={(e) => setSettingsText(e.target.value)}
                />
              </div>
              {error ? <p className="text-sm text-destructive">{error}</p> : null}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="ghost" onClick={onClose} disabled={saving}>
                  取消
                </Button>
                <Button type="button" onClick={handleSave} disabled={saving || !name.trim()}>
                  {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  保存
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
