{**
 * Child Theme classic-fashion - Widoczny stan magazynowy wybranego wariantu na karcie produktu (D3)
 *}
{extends file='parent:catalog/_partials/product-add-to-cart.tpl'}

{block name='product_availability'}
  <span id="product-availability" class="js-product-availability msq-product-availability">
    {if $product.show_availability}
      {if $product.quantity > 0}
        {if $product.availability == 'last_remaining_items'}
          <i class="material-icons product-last-items" aria-hidden="true">&#xE002;</i>
        {else}
          <i class="material-icons rtl-no-flip product-available" aria-hidden="true">&#xE5CA;</i>
        {/if}
        {if $product.availability_message}
          <span>{$product.availability_message}</span>
        {/if}
        {if $product.show_quantities}
          <span class="msq-variant-stock">W magazynie: <strong>{$product.quantity} szt.</strong></span>
        {/if}
      {else}
        <i class="material-icons product-unavailable" aria-hidden="true">&#xE14B;</i>
        <span>{if $product.availability_message}{$product.availability_message}{else}Brak w magazynie{/if}</span>
        {if $product.show_quantities}
          <span class="msq-variant-stock">(0 szt.)</span>
        {/if}
      {/if}
    {/if}
  </span>
{/block}
