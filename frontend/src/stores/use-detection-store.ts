import { create } from "zustand";
import axios from "axios";

import { runDetection } from "@/lib/api/client";
import type { DetectionObject } from "@/types";

interface DetectionState {
  imageFile: File | null;
  imageUrl: string | null;
  rid: string | null;
  objects: DetectionObject[];
  selectedBid: string | null;
  isLoading: boolean;
  error: string | null;
  setImageFile: (file: File | null) => void;
  setSelectedBid: (bid: string | null) => void;
  clear: () => void;
  submitDetection: () => Promise<void>;
}

export const useDetectionStore = create<DetectionState>((set, get) => ({
  imageFile: null,
  imageUrl: null,
  rid: null,
  objects: [],
  selectedBid: null,
  isLoading: false,
  error: null,
  setImageFile: (file: File | null) => {
    const currentUrl = get().imageUrl;
    if (currentUrl?.startsWith("blob:")) {
      URL.revokeObjectURL(currentUrl);
    }

    set({
      imageFile: file,
      imageUrl: file ? URL.createObjectURL(file) : null,
      error: null,
    });
  },
  setSelectedBid: (bid: string | null) => set({ selectedBid: bid }),
  clear: () => {
    const currentUrl = get().imageUrl;
    if (currentUrl?.startsWith("blob:")) {
      URL.revokeObjectURL(currentUrl);
    }

    set({
      imageFile: null,
      imageUrl: null,
      rid: null,
      objects: [],
      selectedBid: null,
      isLoading: false,
      error: null,
    });
  },
  submitDetection: async () => {
    const { imageFile } = get();
    if (!imageFile) {
      set({ error: "請先選擇影像檔案。" });
      return;
    }

    set({ isLoading: true, error: null });
    try {
      const response = await runDetection(imageFile);
      set({
        rid: response.rid,
        objects: response.objects,
        selectedBid: response.objects[0]?.bid ?? null,
        isLoading: false,
      });
    } catch (error) {
      let message = "辨識請求失敗，請稍後再試。";

      if (axios.isAxiosError(error)) {
        if (error.code === "ECONNABORTED") {
          message = "辨識請求逾時，請重試或改用較小影像。";
        } else if (error.code === "ERR_CANCELED") {
          message = "辨識請求已取消，請重新整理後再試。";
        } else {
          const detail = (error.response?.data as { detail?: string; message?: string } | undefined)?.detail
            ?? (error.response?.data as { detail?: string; message?: string } | undefined)?.message;
          if (detail) {
            message = `辨識失敗：${detail}`;
          }
        }
      }

      set({ isLoading: false, error: message });
    }
  },
}));
