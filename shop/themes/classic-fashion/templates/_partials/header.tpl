{**
 * Child Theme classic-fashion - 3-rzedowy naglowek w ukladzie mosquito-sklep.pl (Wariant A)
 *}
{block name='header_banner'}
  <div class="header-banner msq-topbar" role="region" aria-label="{l s='Promocje i dostawa' d='Shop.Theme.Global'}">
    <div class="container">
      <div class="msq-topbar__inner">
        <span>NOWA KOLEKCJA SZYTA W POLSCE &mdash; DARMOWA DOSTAWA OD 2000 ZŁ</span>
      </div>
    </div>
    {hook h='displayBanner'}
  </div>
{/block}

{block name='header_nav'}
  <div class="header-nav msq-header-panel">
    <div class="container">
      <div class="hidden-sm-down msq-panel-desktop">
        <div class="msq-panel-logo" id="_desktop_logo">
          {if $page.page_name == 'index'}
            <h1 class="msq-logo-heading">
              <a href="{$urls.base_url}" class="msq-logo-link" aria-label="Mosquito – Strona główna">
                <span class="sr-only">Mosquito – Moda Damska</span>
                <svg class="msq-logo-svg" viewBox="-2 -2 88 44" width="112" height="36" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <path d="M6.193 28.422h.053l1.967-13.21h4.067v18.606H9.514V20.475h-.053L7.495 33.818H4.731L2.605 20.66H2.55v13.157H0V15.212h4.066l2.127 13.21ZM17.755 29.539c0 1.329.585 1.834 1.515 1.834.93 0 1.515-.505 1.515-1.834V19.492c0-1.329-.585-1.834-1.515-1.834-.93 0-1.515.505-1.515 1.834V29.54Zm-2.924-9.861C14.831 16.7 16.4 15 19.27 15c2.87 0 4.438 1.701 4.438 4.678v9.675c0 2.977-1.568 4.678-4.438 4.678-2.87 0-4.439-1.701-4.439-4.678v-9.675ZM30.194 15c2.844 0 4.306 1.702 4.306 4.678v.585h-2.764v-.77c0-1.33-.532-1.835-1.462-1.835-.93 0-1.462.505-1.462 1.834 0 1.356.585 2.366 2.498 4.04 2.445 2.153 3.216 3.695 3.216 5.821 0 2.977-1.488 4.678-4.359 4.678-2.87 0-4.358-1.701-4.358-4.678V28.21h2.764v1.329c0 1.329.585 1.807 1.515 1.807.93 0 1.515-.478 1.515-1.807 0-1.356-.585-2.365-2.499-4.04-2.445-2.153-3.216-3.694-3.216-5.82 0-2.977 1.462-4.678 4.306-4.678ZM39.55 29.539c0 1.329.585 1.834 1.515 1.834.93 0 1.515-.505 1.515-1.834V19.492c0-1.329-.585-1.834-1.515-1.834-.93 0-1.515.505-1.515 1.834V29.54Zm-2.924-9.861c0-2.977 1.569-4.678 4.439-4.678s4.439 1.701 4.439 4.678v9.675c0 1.036-.186 1.913-.559 2.605.133.345.346.398.824.398h.266v2.605h-.399c-1.302 0-2.126-.478-2.525-1.276a5.993 5.993 0 0 1-2.046.346c-2.87 0-4.439-1.701-4.439-4.678v-9.675ZM50.846 15.212v14.353c0 1.329.584 1.807 1.515 1.807.93 0 1.515-.478 1.515-1.807V15.212h2.764V29.38c0 2.977-1.489 4.678-4.36 4.678-2.87 0-4.358-1.701-4.358-4.678V15.212h2.924ZM62.222 15.212H59.3v18.606h2.923V15.212ZM64.161 15.212h9.037v2.658H70.14v15.948h-2.923V17.87H64.16v-2.658ZM77.823 29.539c0 1.329.585 1.834 1.515 1.834.93 0 1.515-.505 1.515-1.834V19.492c0-1.329-.584-1.834-1.515-1.834-.93 0-1.515.505-1.515 1.834V29.54ZM74.9 19.678C74.9 16.7 76.468 15 79.338 15s4.439 1.701 4.439 4.678v9.675c0 2.977-1.568 4.678-4.439 4.678-2.87 0-4.439-1.701-4.439-4.678v-9.675Z" fill="#111111" transform="translate(0 -10)"/>
                </svg>
              </a>
            </h1>
          {else}
            <div class="msq-logo-heading">
              <a href="{$urls.base_url}" class="msq-logo-link" aria-label="Mosquito – Strona główna">
                <span class="sr-only">Mosquito – Moda Damska</span>
                <svg class="msq-logo-svg" viewBox="-2 -2 88 44" width="112" height="36" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                  <path d="M6.193 28.422h.053l1.967-13.21h4.067v18.606H9.514V20.475h-.053L7.495 33.818H4.731L2.605 20.66H2.55v13.157H0V15.212h4.066l2.127 13.21ZM17.755 29.539c0 1.329.585 1.834 1.515 1.834.93 0 1.515-.505 1.515-1.834V19.492c0-1.329-.585-1.834-1.515-1.834-.93 0-1.515.505-1.515 1.834V29.54Zm-2.924-9.861C14.831 16.7 16.4 15 19.27 15c2.87 0 4.438 1.701 4.438 4.678v9.675c0 2.977-1.568 4.678-4.438 4.678-2.87 0-4.439-1.701-4.439-4.678v-9.675ZM30.194 15c2.844 0 4.306 1.702 4.306 4.678v.585h-2.764v-.77c0-1.33-.532-1.835-1.462-1.835-.93 0-1.462.505-1.462 1.834 0 1.356.585 2.366 2.498 4.04 2.445 2.153 3.216 3.695 3.216 5.821 0 2.977-1.488 4.678-4.359 4.678-2.87 0-4.358-1.701-4.358-4.678V28.21h2.764v1.329c0 1.329.585 1.807 1.515 1.807.93 0 1.515-.478 1.515-1.807 0-1.356-.585-2.365-2.499-4.04-2.445-2.153-3.216-3.694-3.216-5.82 0-2.977 1.462-4.678 4.306-4.678ZM39.55 29.539c0 1.329.585 1.834 1.515 1.834.93 0 1.515-.505 1.515-1.834V19.492c0-1.329-.585-1.834-1.515-1.834-.93 0-1.515.505-1.515 1.834V29.54Zm-2.924-9.861c0-2.977 1.569-4.678 4.439-4.678s4.439 1.701 4.439 4.678v9.675c0 1.036-.186 1.913-.559 2.605.133.345.346.398.824.398h.266v2.605h-.399c-1.302 0-2.126-.478-2.525-1.276a5.993 5.993 0 0 1-2.046.346c-2.87 0-4.439-1.701-4.439-4.678v-9.675ZM50.846 15.212v14.353c0 1.329.584 1.807 1.515 1.807.93 0 1.515-.478 1.515-1.807V15.212h2.764V29.38c0 2.977-1.489 4.678-4.36 4.678-2.87 0-4.358-1.701-4.358-4.678V15.212h2.924ZM62.222 15.212H59.3v18.606h2.923V15.212ZM64.161 15.212h9.037v2.658H70.14v15.948h-2.923V17.87H64.16v-2.658ZM77.823 29.539c0 1.329.585 1.834 1.515 1.834.93 0 1.515-.505 1.515-1.834V19.492c0-1.329-.584-1.834-1.515-1.834-.93 0-1.515.505-1.515 1.834V29.54ZM74.9 19.678C74.9 16.7 76.468 15 79.338 15s4.439 1.701 4.439 4.678v9.675c0 2.977-1.568 4.678-4.439 4.678-2.87 0-4.439-1.701-4.439-4.678v-9.675Z" fill="#111111" transform="translate(0 -10)"/>
                </svg>
              </a>
            </div>
          {/if}
        </div>
        <div class="msq-panel-tools right-nav">
          {hook h='displayNav2'}
        </div>
      </div>

      <div class="hidden-md-up mobile msq-mobile-bar">
        <div class="top-logo" id="_mobile_logo"></div>
        <div class="msq-mobile-actions">
          <div id="_mobile_user_info"></div>
          <div id="_mobile_cart"></div>
          <button type="button" class="msq-menu-btn" id="menu-icon" aria-label="Menu">
            <i class="material-icons d-inline" aria-hidden="true">&#xE5D2;</i>
          </button>
        </div>
      </div>
    </div>
  </div>
{/block}

{block name='header_top'}
  <div class="header-top msq-nav-search-bar">
    <div class="container">
      <div class="msq-top-flex">
        {hook h='displayTop'}
      </div>
      <div id="mobile_top_menu_wrapper" class="row hidden-md-up" style="display:none;">
        <div class="js-top-menu mobile" id="_mobile_top_menu"></div>
        <div class="js-top-menu-bottom">
          <div id="_mobile_currency_selector"></div>
          <div id="_mobile_language_selector"></div>
          <div id="_mobile_contact_link"></div>
        </div>
      </div>
    </div>
  </div>
  {hook h='displayNavFullWidth'}
{/block}
