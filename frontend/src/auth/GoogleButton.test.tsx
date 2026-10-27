import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GoogleButton } from "./GoogleButton";

describe("GoogleButton", () => {
  it("não aparece nem carrega o script do Google sem Client ID configurado", () => {
    const { container } = render(<GoogleButton onCredential={() => {}} />);
    expect(container).toBeEmptyDOMElement();
    expect(document.querySelector('script[src*="accounts.google.com"]')).toBeNull();
  });
});
