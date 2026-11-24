{**
 * Moduł ps_omnibusprice – informacja o najniższej cenie z 30 dni przed obniżką (Dyrektywa Omnibus, D3)
 *}
{if !empty($omnibus_text)}
  <div class="ps-omnibus-price omnibus-price{if $omnibus_context === 'list'} ps-omnibus-price--list{else} ps-omnibus-price--sheet{/if}" data-omnibus-price="{$omnibus_raw|escape:'html_attr'}">
    <span class="ps-omnibus-price__text">{$omnibus_text}</span>
  </div>
{/if}
