// frontend/src/services/api.js

import axios from "axios";

/**
 * Centralized Axios instance.
 */
const api = axios.create({
  baseURL: "http://127.0.0.1:8000",
  timeout: 30000,
  headers: {
    Accept: "application/json",
  },
});

/**
 * Upload resume file.
 *
 * @param {File} file
 * @returns {Promise<Object>}
 */
export const uploadResume = async (file) => {
  try {
    const formData = new FormData();
    formData.append("file", file);

    const response = await api.post(
      "/resume/upload",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );

    return response.data;
  } catch (error) {
    console.error("Resume upload failed:", error);

    if (error.response) {
      throw new Error(
        error.response.data?.detail ||
          "Server error while uploading resume."
      );
    }

    if (error.request) {
      throw new Error(
        "Unable to connect to backend server."
      );
    }

    throw new Error(
      error.message || "Unexpected upload error."
    );
  }
};

export default api;
