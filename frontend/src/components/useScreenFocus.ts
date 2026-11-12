"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Focus and announce screen changes (Spec 04 FR-RV-21): when `key` changes, move focus
 * to the new screen's heading and put `message` in a polite live region. Nothing happens
 * on first render, so a page load never steals focus.
 *
 * With `immediate: false` the caller decides when the new heading exists (e.g. after an
 * enter animation) and calls `focus()`; the heading is found via `headingRef` or, if no
 * ref is attached, as the first `h1` inside `#main`.
 */
export function useScreenFocus(key: string, message: string, { immediate = true } = {}) {
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const first = useRef(true);
  const pending = useRef(false);

  const focus = useCallback(() => {
    if (!pending.current) return;
    const heading = headingRef.current ?? document.querySelector<HTMLElement>("#main h1");
    if (!heading) return;
    if (!heading.hasAttribute("tabindex")) heading.setAttribute("tabindex", "-1");
    heading.focus();
    pending.current = false;
  }, []);

  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    pending.current = true;
    setAnnouncement(message);
    if (immediate) focus();
    // Only a change of screen (key) triggers this; message/focus are read at that moment.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { headingRef, announcement, focus };
}
