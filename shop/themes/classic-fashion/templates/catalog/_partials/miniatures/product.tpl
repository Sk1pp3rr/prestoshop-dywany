{**
 * Child Theme classic-fashion - Karta produktu 3:4 w stylu mosquito-sklep.pl
 * Pastylki flag w lewym dolnym rogu zdjecia, tytul + cena po lewej i ikona torebki po prawej.
 *}
{block name='product_miniature_item'}
<div class="js-product product{if !empty($productClasses)} {$productClasses}{/if}">
  <article class="product-miniature js-product-miniature" data-id-product="{$product.id_product}" data-id-product-attribute="{$product.id_product_attribute}">
    <div class="thumbnail-container">
      <div class="thumbnail-top">
        {block name='product_thumbnail'}
          {if $product.cover}
            <a href="{$product.url}" class="thumbnail product-thumbnail">
              <picture>
                {if !empty($product.cover.bySize.home_default.sources.avif)}<source srcset="{$product.cover.bySize.home_default.sources.avif}" type="image/avif">{/if}
                {if !empty($product.cover.bySize.home_default.sources.webp)}<source srcset="{$product.cover.bySize.home_default.sources.webp}" type="image/webp">{/if}
                <img
                  src="{$product.cover.bySize.home_default.url}"
                  alt="{if !empty($product.cover.legend)}{$product.cover.legend|escape:'html_attr'}{else}{$product.name|escape:'html_attr'}{/if}"
                  loading="lazy"
                  data-full-size-image-url="{$product.cover.large.url}"
                  width="360"
                  height="480"
                />
              </picture>
            </a>
          {else}
            <a href="{$product.url}" class="thumbnail product-thumbnail">
              <picture>
                <img
                  src="{$urls.no_picture_image.bySize.home_default.url}"
                  alt="{$product.name|escape:'html_attr'}"
                  loading="lazy"
                  width="360"
                  height="480"
                />
              </picture>
            </a>
          {/if}
        {/block}

        {include file='catalog/_partials/product-flags.tpl'}

        {if $product.main_variants}
          <div class="highlighted-informations msq-card-variants">
            {block name='product_variants'}
              {include file='catalog/_partials/variant-links.tpl' variants=$product.main_variants}
            {/block}
          </div>
        {/if}
      </div>

      <div class="product-description">
        <div class="msq-card-row">
          <div class="msq-card-info">
            {block name='product_name'}
              {if $page.page_name == 'index'}
                <h3 class="h3 product-title"><a href="{$product.url}" content="{$product.url}">{$product.name|truncate:60:'...'}</a></h3>
              {else}
                <h2 class="h3 product-title"><a href="{$product.url}" content="{$product.url}">{$product.name|truncate:60:'...'}</a></h2>
              {/if}
            {/block}

            {block name='product_price_and_shipping'}
              {if $product.show_price}
                <div class="product-price-and-shipping">
                  {if $product.has_discount}
                    {hook h='displayProductPriceBlock' product=$product type="old_price"}
                    <span class="regular-price">{$product.regular_price}</span>
                    {if $product.discount_type === 'percentage'}
                      <span class="discount-percentage discount-product">{$product.discount_percentage}</span>
                    {elseif $product.discount_type === 'amount'}
                      <span class="discount-amount discount-product">{$product.discount_amount_to_display}</span>
                    {/if}
                  {/if}

                  {hook h='displayProductPriceBlock' product=$product type="before_price"}
                  <span class="price">
                    {capture name='custom_price'}{hook h='displayProductPriceBlock' product=$product type='custom_price' hook_origin='products_list'}{/capture}
                    {if '' !== $smarty.capture.custom_price}
                      {$smarty.capture.custom_price nofilter}
                    {else}
                      {$product.price}
                    {/if}
                  </span>

                  {hook h='displayProductPriceBlock' product=$product type='unit_price'}
                  {hook h='displayProductPriceBlock' product=$product type='weight'}
                </div>
              {/if}
            {/block}
          </div>

          {block name='quick_view'}
            <a class="quick-view js-quick-view msq-bag-btn" href="#" data-link-action="quickview" aria-label="Szybki podgląd: {$product.name|escape:'html_attr'}">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M6 7h12l-1 13H7L6 7z"/>
                <path d="M9 7V6a3 3 0 0 1 6 0v1"/>
              </svg>
            </a>
          {/block}
        </div>

        {block name='product_reviews'}
          {hook h='displayProductListReviews' product=$product}
        {/block}
      </div>
    </div>
  </article>
</div>
{/block}
