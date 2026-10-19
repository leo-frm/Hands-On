-- Ajusta o HTML do relatorio para o .docx: capa, quebras de pagina e estilos
local PB = pandoc.RawBlock('openxml', '<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

local function has(el, cls)
  for _, c in ipairs(el.classes or {}) do if c == cls then return true end end
  return false
end

function Header(h)
  if has(h, 't') then
    return pandoc.Div({pandoc.Para(h.content)}, {['custom-style'] = 'Title'})
  end
  if has(h, 'pb') then
    return {PB, h}
  end
end

function Div(d)
  if has(d, 'cover') then
    local out = {}
    for _, b in ipairs(d.content) do table.insert(out, b) end
    table.insert(out, PB)
    return out
  end
  if has(d, 'sub') then d.attributes['custom-style'] = 'Subtitle'; return d end
  if has(d, 'inst') or has(d, 'who') then d.attributes['custom-style'] = 'Capa'; return d end
  if has(d, 'info') then d.attributes['custom-style'] = 'Destaque'; return d end
end

function Para(p)
  return p
end

function Blocks(blocks)
  -- <p class="note"> chega como Div com classe note
  return blocks
end

local base_div = Div
function Div(d)
  local cls = d.classes or {}
  for _, c in ipairs(cls) do
    if c == 'note' then d.attributes['custom-style'] = 'Nota'; return d end
  end
  return base_div(d)
end
