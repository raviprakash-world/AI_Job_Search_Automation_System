from app.browser_automation.field_matching import DiscoveredField

# Finds every input/textarea/select inside the form and its best-guess label,
# trying (in order): an explicit <label for="id">, then the nearest ancestor
# wrapper's label-like element — covers both Greenhouse's id-based <label for>
# convention and Lever's name-based fields wrapped in a labeled container.
_DISCOVER_FIELDS_JS = """
() => {
  const form = document.querySelector('form');
  if (!form) return [];
  const elements = Array.from(form.querySelectorAll('input, textarea, select'));
  return elements.map((el, index) => {
    let label = null;
    if (el.id) {
      const byFor = document.querySelector(`label[for="${el.id}"]`);
      if (byFor) label = byFor.innerText;
    }
    if (!label) {
      const wrapper = el.closest('.application-question, .field, li, .card, div');
      if (wrapper) {
        const candidate = wrapper.querySelector('label, .application-label');
        if (candidate) label = candidate.innerText;
      }
    }
    const handle = el.id || el.name || `__field_${index}`;
    return {
      handle,
      selector: el.id ? `#${CSS.escape(el.id)}` : (el.name ? `[name="${CSS.escape(el.name)}"]` : null),
      index,
      label,
      field_type: (el.tagName === 'TEXTAREA') ? 'textarea' : (el.tagName === 'SELECT' ? 'select' : (el.type || 'text')),
    };
  });
}
"""


async def discover_fields(page) -> list[dict]:
    """Returns raw field descriptors (handle/selector/index/label/field_type)
    from the live page — kept separate from field_matching.py so the matching
    logic stays pure and unit-testable without a browser."""
    raw = await page.evaluate(_DISCOVER_FIELDS_JS)
    return raw


def to_discovered_fields(raw_fields: list[dict]) -> list[DiscoveredField]:
    return [
        DiscoveredField(handle=f["handle"], label=f.get("label"), field_type=f["field_type"], index=f["index"])
        for f in raw_fields
    ]
