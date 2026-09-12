--[[
crossref.lua — numera figuras e tabelas e resolve @fig:x / @tbl:x (ADR-0035).

Roda ANTES de --citeproc: toda referência vira texto aqui, então nenhuma
chega ao citeproc (citekey ausente) nem ao zotero_live_docx.lua.

Sintaxe (a mesma do pandoc-crossref):
  ![Legenda](figures/x.png){#fig:x}
  : Legenda {#tbl:x}          (linha de legenda sob a tabela)
  Ver @fig:x e @tbl:x.        (solto, fora de colchetes)

Rótulo: meta.lang (frontmatter) > meta.prumo_lang ([writing].language).
]]--

local LABELS = {
  pt = { fig = 'Figura', tbl = 'Tabela' },
  en = { fig = 'Figure', tbl = 'Table' },
}
local SEQ = { fig = 'Figure', tbl = 'Table' }
local NBSP = '\u{A0}'

local function caption_prefix(label, kind, n)
  if FORMAT == 'docx' then
    return { pandoc.RawInline('openxml', string.format(
      '<w:r><w:t xml:space="preserve">%s </w:t></w:r>'
      .. '<w:fldSimple w:instr=" SEQ %s \\* ARABIC "><w:r><w:t>%d</w:t></w:r></w:fldSimple>'
      .. '<w:r><w:t xml:space="preserve">: </w:t></w:r>', label, SEQ[kind], n)) }
  end
  return { pandoc.Str(label .. NBSP .. n .. ':'), pandoc.Space() }
end

local function prefix_caption(caption, inlines)
  local first = caption.long[1]
  if first and (first.t == 'Plain' or first.t == 'Para') then
    first.content = inlines .. first.content
  else
    caption.long:insert(1, pandoc.Plain(inlines))
  end
end

function Pandoc(doc)
  local lang = pandoc.utils.stringify(doc.meta.lang or doc.meta.prumo_lang or 'en-US')
  local labels = LABELS[lang:sub(1, 2):lower()] or LABELS.en
  local counts, refs = { fig = 0, tbl = 0 }, {}

  local function number(el, kind)
    if #el.caption.long == 0 then
      return nil
    end
    counts[kind] = counts[kind] + 1
    if el.identifier ~= '' then
      refs[el.identifier] = labels[kind] .. NBSP .. counts[kind]
    end
    if FORMAT ~= 'typst' then -- o #figure do Typst já numera
      prefix_caption(el.caption, pandoc.Inlines(caption_prefix(labels[kind], kind, counts[kind])))
    end
    return el
  end

  doc = doc:walk({
    Figure = function(el) return number(el, 'fig') end,
    Table = function(el) return number(el, 'tbl') end,
  })

  return doc:walk({
    Cite = function(cite)
      local id, hits = nil, 0
      for _, c in ipairs(cite.citations) do
        if c.id:match('^fig:') or c.id:match('^tbl:') then
          id, hits = c.id, hits + 1
        end
      end
      if not id then
        return nil
      end
      local head = cite.citations[1]
      if hits ~= 1 or head.id ~= id or head.mode ~= 'AuthorInText' then
        error('crossref: [@' .. id .. '] entre colchetes ou junto de citekey. Escreva @'
          .. id .. ' solto, fora de colchetes, e rode `prumo write export` de novo.')
      end
      if not refs[id] then
        error('crossref: @' .. id .. ' não tem alvo. Marque a figura com '
          .. '![legenda](arquivo.png){#' .. id .. '} ou a tabela com `: legenda {#'
          .. id .. '}` e rode `prumo write export` de novo.')
      end
      if #cite.citations == 1 then
        return pandoc.Str(refs[id])
      end
      -- `@fig:x [@key]`: o Pandoc funde os dois num Cite só; separa a citação real.
      local rest = pandoc.List()
      for i = 2, #cite.citations do
        rest:insert(cite.citations[i])
      end
      return { pandoc.Str(refs[id]), pandoc.Space(), pandoc.Cite({}, rest) }
    end,
  })
end
