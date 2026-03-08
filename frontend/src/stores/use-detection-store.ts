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
      set({ error: "Please select an image file first." });
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
      let message = "Detection request failed. Please try again.";

      if (axios.isAxiosError(error)) {
        if (error.code === "ECONNABORTED") {
          message = "Detection request timed out. Try again or use a smaller image.";
        } else if (error.code === "ERR_CANCELED") {
          message = "Detection request was canceled. Refresh and try again.";
        } else {
          const detail = (error.response?.data as { detail?: string; message?: string } | undefined)?.detail
            ?? (error.response?.data as { detail?: string; message?: string } | undefined)?.message;
          if (detail) {
            message = `Detection failed: ${detail}`;
          }
        }
      }

      set({ isLoading: false, error: message });
    }
  },
}));
