{**
 * Child Theme classic-fashion - Strona glowna w ukladzie mosquito-sklep.pl (Wariant A)
 *}
{extends file='page.tpl'}

{block name='page_content_container'}
  <section id="content" class="page-home">
    {block name='page_content_top'}{/block}

    {block name='page_content'}
      <div class="msq-home-canvas">
        {block name='hook_home'}
          {$HOOK_HOME nofilter}
        {/block}
      </div>
    {/block}
  </section>
{/block}
