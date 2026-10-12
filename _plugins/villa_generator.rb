require 'json'

module Jekyll
  module VText
    module_function

    def hangul_tail?(s)
      c = s.to_s.strip.sub(/[\s\)\]\}\>'"”’.,!?~·\-]+\z/, '')[-1]
      !c.nil? && c.ord >= 0xAC00 && c.ord <= 0xD7A3
    end

    def batchim?(s)
      c = s.to_s.strip.sub(/[\s\)\]\}\>'"”’.,!?~·\-]+\z/, '')[-1]
      return false if c.nil?
      o = c.ord
      (o >= 0xAC00 && o <= 0xD7A3) ? ((o - 0xAC00) % 28 != 0) : false
    end

    def josa(word, with_b, without_b)
      return "#{word}#{with_b}(#{without_b})" unless hangul_tail?(word)
      word.to_s + (batchim?(word) ? with_b : without_b)
    end

    def eun_neun(w); josa(w, '은', '는'); end

    def fmt(n)
      n.to_i.to_s.reverse.scan(/\d{1,3}/).join(',').reverse
    end

    # 만원 단위 -> "12억 3,500만원"
    def man(n)
      n = n.to_i
      return '-' if n <= 0
      eok = n / 10_000
      rest = n % 10_000
      if eok.positive?
        rest.zero? ? "#{eok}억원" : "#{eok}억 #{fmt(rest)}만원"
      else
        "#{fmt(n)}만원"
      end
    end

    def date(ymd)
      y = ymd.to_i / 10_000
      m = (ymd.to_i / 100) % 100
      d = ymd.to_i % 100
      format('%04d.%02d.%02d', y, m, d)
    end

    def area(a)
      a.to_f == a.to_f.round ? a.to_f.round.to_s : format('%.1f', a.to_f)
    end

    def median(arr)
      return 0 if arr.empty?
      s = arr.sort
      s[s.size / 2]
    end
  end

  class VillaGenerator < Generator
    safe true
    priority :normal

    KIND = { 'v' => '빌라', 'o' => '오피스텔' }.freeze
    MAX_BUILDING_PAGES = 38_000      # 용량(Pages 1GB) 때문에 거래가 많은 건물만 상세 페이지를 만든다. 나머지는 동 허브 표에만 나온다.
    DONG_ROWS = 120
    SEARCH_MAX = 30_000

    def generate(site)
      dir = File.join(site.source, '_rawdata')
      bs = []
      Dir.glob(File.join(dir, 'villa_*.json')).sort.each do |f|
        next if f.end_with?('villa_meta.json')
        bs.concat(JSON.parse(File.read(f, encoding: 'utf-8')))
      end
      meta = JSON.parse(File.read(File.join(dir, 'villa_meta.json'), encoding: 'utf-8'))
      latest = VText.date(meta['latest'])

      bs.each do |b|
        b['rep'] = b['tg'].first
        rg = b['rg'].find { |g| b['rep'] && g['a'] == b['rep']['a'] && g['ratio'].to_i.positive? } || b['rg'].find { |g| g['ratio'].to_i.positive? }
        b['ratio'] = rg ? rg['ratio'].to_i : 0
        b['ratioA'] = rg ? rg['a'] : 0
        b['score'] = b['n36'] + b['nr24']
      end

      ranked = bs.sort_by { |b| [-b['score'], -b['last'], b['id']] }
      page_set = ranked.first(MAX_BUILDING_PAGES)
      page_set.each { |b| b['url'] = "/b/#{b['slug']}/" }

      by_dong = bs.group_by { |b| [b['doShort'], b['sigungu'], b['dong']] }
      by_sg = bs.group_by { |b| [b['doShort'], b['sigungu']] }
      by_do = bs.group_by { |b| b['doShort'] }

      counts = Hash.new(0)
      page_set.each do |b|
        neighbors = by_dong[[b['doShort'], b['sigungu'], b['dong']]].select { |x| x['url'] && x['id'] != b['id'] }.sort_by { |x| -x['score'] }.first(8)
        site.pages << BuildingPage.new(site, b, neighbors, latest)
        counts[:building] += 1
      end

      by_do.keys.sort.each do |do_short|
        list = by_do[do_short]
        sgs = list.group_by { |b| b['sigungu'] }
        sg_rows = sgs.map { |sg, l| { 'name' => sg, 'n' => l.size, 'villa' => l.count { |b| b['kind'] == 'v' }, 'offi' => l.count { |b| b['kind'] == 'o' }, 'stat' => VillaGenerator.stat(l) } }.sort_by { |h| [-h['n'], h['name']] }
        site.pages << DoHubPage.new(site, do_short, sg_rows, list, latest)
        counts[:do] += 1
        sgs.each do |sg, l|
          dongs = l.group_by { |b| b['dong'] }
          dong_rows = dongs.map { |dg, dl| { 'name' => dg, 'n' => dl.size, 'villa' => dl.count { |b| b['kind'] == 'v' }, 'offi' => dl.count { |b| b['kind'] == 'o' }, 'stat' => VillaGenerator.stat(dl) } }.sort_by { |h| [-h['n'], h['name']] }
          site.pages << SgHubPage.new(site, do_short, sg, l, dong_rows, latest)
          counts[:sg] += 1
          dongs.each do |dg, dl|
            next if dl.size < 2
            site.pages << DongHubPage.new(site, do_short, sg, dg, dl, dong_rows, latest)
            counts[:dong] += 1
          end
        end
        ranked_j = VillaGenerator.jeonse_list(list)
        site.pages << JeonsePage.new(site, do_short, ranked_j, latest)
        counts[:jeonse] += 1
      end
      site.pages << JeonsePage.new(site, nil, VillaGenerator.jeonse_list(bs), latest)

      do_rows = by_do.keys.sort.map do |d|
        l = by_do[d]
        { 'name' => d, 'n' => VText.fmt(l.size), 'villa' => VText.fmt(l.count { |b| b['kind'] == 'v' }), 'offi' => VText.fmt(l.count { |b| b['kind'] == 'o' }) }
      end
      busy_dongs = by_dong.select { |_, l| l.size >= 2 }.sort_by { |_, l| -l.sum { |b| b['score'] } }.first(24).map do |(d, s, g), l|
        { 'label' => "#{d} #{s} #{g}", 'url' => "/region/#{d}/#{s}/#{g}/", 'n' => VText.fmt(l.size) }
      end
      site.data['villa_stats'] = {
        'total' => VText.fmt(bs.size), 'villa' => VText.fmt(bs.count { |b| b['kind'] == 'v' }), 'offi' => VText.fmt(bs.count { |b| b['kind'] == 'o' }),
        'pages' => VText.fmt(page_set.size), 'latest' => latest, 'do_rows' => do_rows, 'busy_dongs' => busy_dongs,
        'top_active' => page_set.first(12).map { |b| VillaGenerator.row(b) }
      }

      idx = []
      by_dong.each { |(d, s, g), l| idx << { 'n' => g, 't' => '동네', 'l' => "#{d} #{s}", 'u' => "/region/#{d}/#{s}/#{g}/" } if l.size >= 2 }
      by_sg.each_key { |d, s| idx << { 'n' => s, 't' => '시군구', 'l' => d, 'u' => "/region/#{d}/#{s}/" } }
      page_set.first(SEARCH_MAX).each { |b| idx << { 'n' => b['name'], 't' => KIND[b['kind']], 'l' => "#{b['doShort']} #{b['sigungu']} #{b['dong']}", 'u' => b['url'] } }
      pg = PageWithoutAFile.new(site, site.source, '', 'search_index.json')
      pg.content = JSON.generate(idx)
      pg.data['layout'] = nil
      pg.data['sitemap'] = false
      site.pages << pg
      Jekyll.logger.info 'VillaGenerator:', "건물 #{counts[:building]} / 동 #{counts[:dong]} / 시군구 #{counts[:sg]} / 시도 #{counts[:do]} / 전세가율 #{counts[:jeonse] + 1} (전체 건물 레코드 #{bs.size})"
    end

    # 목록용 한 줄
    def self.row(b)
      rep = b['rep']
      {
        'name' => b['name'], 'url' => b['url'], 'kind' => KIND[b['kind']], 'ht' => b['ht'], 'by' => b['by'].to_i, 'jibun' => b['jibun'],
        'loc' => "#{b['doShort']} #{b['sigungu']} #{b['dong']}",
        'n' => b['n36'], 'nr' => b['nr24'], 'last' => VText.date(b['last']),
        'rep' => rep ? "전용 #{rep['a']}㎡ 평균 #{VText.man(rep['avg36'])}" : '-',
        'ratio' => b['ratio'].positive? ? "#{b['ratio']}%" : '-'
      }
    end

    def self.stat(list)
      reps = list.select { |b| b['rep'] }
      ratios = list.map { |b| b['ratio'] }.select { |r| r >= 20 && r <= 150 }
      {
        'median' => reps.empty? ? '-' : VText.man(VText.median(reps.map { |b| b['rep']['avg36'] })),
        'ratio' => ratios.size >= 3 ? "#{(ratios.sum.to_f / ratios.size).round}%" : '-',
        'ratioN' => ratios.size,
        'tx' => list.sum { |b| b['n36'] + b['nr24'] }
      }
    end

    # 전세가율 참고 목록(신뢰도를 위해 전세·매매가 각각 2건 이상 있는 건물만)
    def self.jeonse_list(list)
      list.select do |b|
        b['url'] && b['ratio'] >= 70 && b['ratio'] <= 130 &&
          b['rg'].any? { |g| g['a'] == b['ratioA'] && g['nj'] >= 2 } && b['tg'].any? { |g| g['a'] == b['ratioA'] && g['n24'] >= 2 }
      end.sort_by { |b| [-b['ratio'], -b['score']] }
    end
  end

  class VBasePage < Page
    def setup(site, dir, layout)
      @site = site
      @base = site.source
      @dir = dir
      @name = 'index.html'
      process(@name)
      read_yaml(File.join(@base, '_layouts'), "#{layout}.html")
      data['layout'] = layout
    end

    def seo(title, desc)
      data['title'] = title
      data['description'] = desc[0, 155]
    end

    def faq(pairs)
      data['faq'] = pairs.map { |q, a| { 'q' => q, 'a' => a } }
    end

    def f(n)
      VText.fmt(n)
    end
  end

  # ── 건물 상세 ───────────────────────────────────────
  class BuildingPage < VBasePage
    def initialize(site, b, neighbors, latest)
      setup(site, "b/#{b['slug']}", 'building')
      name = b['name']
      kind = VillaGenerator::KIND[b['kind']]
      loc = "#{b['doShort']} #{b['sigungu']} #{b['dong']}"
      rep = b['rep']
      data['bName'] = name
      data['doShort'] = b['doShort']
      data['sigungu'] = b['sigungu']
      data['dong'] = b['dong']
      data['jibun'] = b['jibun']
      data['kind'] = kind
      data['ht'] = b['ht']
      data['by'] = b['by'].to_i
      data['n36'] = b['n36']
      data['nr24'] = b['nr24']
      data['latest'] = latest
      data['tgRows'] = b['tg'].map do |g|
        rg = b['rg'].find { |x| x['a'] == g['a'] }
        { 'a' => g['a'], 'py' => g['py'], 'n36' => g['n36'], 'avg' => VText.man(g['avg36']), 'min' => VText.man(g['min36']), 'max' => VText.man(g['max36']), 'maxd' => VText.date(g['maxd']),
          'last' => "#{VText.date(g['last'][0])} #{g['last'][1]}층 #{VText.man(g['last'][2])}",
          'nj' => rg ? rg['nj'] : 0, 'avgj' => rg && rg['avgj'].positive? ? VText.man(rg['avgj']) : '-',
          'nw' => rg ? rg['nw'] : 0, 'avgw' => rg && rg['nw'].positive? ? "#{VText.man(rg['avgwd'])} / #{VText.fmt(rg['avgwm'])}만원" : '-',
          'ratio' => rg && rg['ratio'].to_i.positive? ? "#{rg['ratio']}%" : '-' }
      end
      only_rent = b['rg'].reject { |g| b['tg'].any? { |t| t['a'] == g['a'] } }
      data['rentOnly'] = only_rent.map do |g|
        { 'a' => g['a'], 'nj' => g['nj'], 'avgj' => g['avgj'].positive? ? VText.man(g['avgj']) : '-', 'nw' => g['nw'], 'avgw' => g['nw'].positive? ? "#{VText.man(g['avgwd'])} / #{VText.fmt(g['avgwm'])}만원" : '-' }
      end
      data['tRows'] = b['t'].map { |r| { 'd' => VText.date(r[0]), 'a' => VText.area(r[1]), 'f' => r[2], 'amt' => VText.man(r[3]) } }
      data['rRows'] = b['r'].map do |r|
        { 'd' => VText.date(r[0]), 'a' => VText.area(r[1]), 'f' => r[2], 'type' => r[4].to_i.zero? ? '전세' : '월세', 'dep' => VText.man(r[3]), 'mon' => r[4].to_i.zero? ? '-' : "#{VText.fmt(r[4])}만원", 'c' => r[5] }
      end
      data['yrRows'] = b['yr'].map { |y, n, avg| { 'y' => y, 'n' => n, 'avg' => VText.man(avg) } }
      data['yrArea'] = rep ? rep['a'] : 0
      ratio = b['ratio']
      data['ratio'] = ratio
      data['ratioA'] = b['ratioA']
      data['ratioLevel'] = ratio >= 90 ? 'high' : (ratio >= 80 ? 'warn' : (ratio.positive? ? 'ok' : 'none'))
      data['neighbors'] = neighbors.map { |x| VillaGenerator.row(x) }
      data['aaptUrl'] = "https://wooaapt.wooahouse.com/region/#{b['doShort']}/#{b['sigungu']}/#{b['dong']}/"
      data['hakUrl'] = "https://wooahakgun.wooahouse.com/region/#{b['doShort']}/#{b['sigungu']}/"

      s = +"#{VText.eun_neun(name)} #{loc} #{b['jibun']}에 있는 #{b['ht']}"
      s << "(#{b['by']}년 준공)" if b['by'].to_i.positive?
      s << '입니다. '
      s << "최근 3년간 매매 #{b['n36']}건" if b['n36'].positive?
      s << (b['n36'].positive? && b['nr24'].positive? ? ', ' : '') + "최근 2년간 전월세 #{b['nr24']}건" if b['nr24'].positive?
      s << '이 신고됐습니다. '
      if rep
        s << "가장 거래가 많은 전용 #{rep['a']}㎡(약 #{rep['py']}평형)의 평균 매매가는 #{VText.man(rep['avg36'])}"
        s << "(최저 #{VText.man(rep['min36'])}, 최고 #{VText.man(rep['max36'])})"
        s << "이고, 가장 최근 거래는 #{VText.date(rep['last'][0])} #{rep['last'][1]}층 #{VText.man(rep['last'][2])}입니다. "
      end
      rgm = b['rg'].find { |g| g['a'] == b['ratioA'] }
      if ratio.positive? && rgm
        s << "같은 전용 #{b['ratioA']}㎡의 최근 2년 평균 전세 보증금은 #{VText.man(rgm['avgj'])}으로, 전세가율은 약 #{ratio}%입니다."
      elsif b['nr24'].positive?
        s << '전세·월세 거래는 있지만 같은 면적의 매매 거래가 부족해 전세가율은 계산하지 못했습니다.'
      end
      data['summary'] = s

      seo("#{name} 실거래가·전세가율 | #{loc} #{b['jibun']}", "#{loc} #{name} #{b['ht']} 실거래가. 매매 #{b['n36']}건·전월세 #{b['nr24']}건, #{rep ? "전용 #{rep['a']}㎡ 평균 #{VText.man(rep['avg36'])}" : ''}#{ratio.positive? ? ", 전세가율 #{ratio}%" : ''}.")
      pairs = []
      pairs << ["#{name} 전세가율은 얼마인가요?", ratio.positive? && rgm ? "같은 전용 #{b['ratioA']}㎡ 기준 최근 2년 평균 전세 보증금 #{VText.man(rgm['avgj'])}을 최근 2년 평균 매매가로 나눈 값이 약 #{ratio}%입니다. 거래 건수가 적으면 실제와 차이가 클 수 있습니다." : '같은 전용면적의 매매와 전세 거래가 모두 충분하지 않아 전세가율을 계산하지 못했습니다.']
      pairs << ["#{name} 실거래가는 어디서 확인하나요?", "국토교통부 실거래가 공개시스템에서 확인할 수 있습니다. 이 페이지는 공공데이터포털의 신고 자료를 건물(법정동+지번) 단위로 집계한 것이며, 호수와 거래 당사자는 공개되지 않습니다."]
      pairs << ['전세가율이 높으면 위험한가요?', '전세가율이 높을수록 매매가가 떨어졌을 때 보증금을 돌려받기 어려워질 수 있어 일반적으로 주의가 필요합니다. 다만 선순위 근저당·보증금 합계에 따라 달라지므로 계약 전 등기부등본과 전세보증보험 가입 가능 여부를 반드시 확인하세요.']
      faq(pairs)
    end
  end

  # ── 지역 허브 ───────────────────────────────────────
  class DoHubPage < VBasePage
    def initialize(site, do_short, sg_rows, list, latest)
      setup(site, "region/#{do_short}", 'do')
      data['doShort'] = do_short
      data['sgRows'] = sg_rows.map { |h| { 'name' => h['name'], 'n' => f(h['n']), 'villa' => f(h['villa']), 'offi' => f(h['offi']), 'median' => h['stat']['median'], 'ratio' => h['stat']['ratio'] } }
      data['nTotal'] = f(list.size)
      data['top'] = list.select { |b| b['url'] }.sort_by { |b| -b['score'] }.first(15).map { |b| VillaGenerator.row(b) }
      st = VillaGenerator.stat(list)
      data['stat'] = st
      data['latest'] = latest
      data['summary'] = "#{do_short}의 연립다세대(빌라)·오피스텔 #{f(list.size)}개 건물의 최근 3년 매매와 최근 2년 전월세 실거래가를 정리했습니다. 건물별 대표 평형 평균 매매가의 중앙값은 #{st['median']}이고, 평균 전세가율은 #{st['ratio']}입니다. 시군구를 선택해 동네별 실거래가를 확인하세요."
      seo("#{do_short} 빌라·오피스텔 실거래가 - 시군구별 매매·전세가율", "#{do_short} 연립다세대·오피스텔 #{f(list.size)}개 건물의 매매·전월세 실거래가와 전세가율. 시군구별 중앙 매매가와 평균 전세가율.")
    end
  end

  class SgHubPage < VBasePage
    def initialize(site, do_short, sg, list, dong_rows, latest)
      setup(site, "region/#{do_short}/#{sg}", 'sigungu')
      data['doShort'] = do_short
      data['sigungu'] = sg
      data['nTotal'] = f(list.size)
      data['nVilla'] = f(list.count { |b| b['kind'] == 'v' })
      data['nOffi'] = f(list.count { |b| b['kind'] == 'o' })
      st = VillaGenerator.stat(list)
      data['stat'] = st
      data['latest'] = latest
      data['dongRows'] = dong_rows.map { |h| { 'name' => h['name'], 'n' => f(h['n']), 'villa' => f(h['villa']), 'offi' => f(h['offi']), 'median' => h['stat']['median'], 'ratio' => h['stat']['ratio'], 'hub' => h['n'] >= 2 } }
      data['top'] = list.select { |b| b['url'] }.sort_by { |b| -b['score'] }.first(20).map { |b| VillaGenerator.row(b) }
      data['summary'] = "#{do_short} #{sg}의 빌라(연립·다세대)·오피스텔 #{f(list.size)}개 건물을 정리했습니다(빌라 #{data['nVilla']}곳, 오피스텔 #{data['nOffi']}곳). 건물별 대표 평형 평균 매매가의 중앙값은 #{st['median']}, 평균 전세가율은 #{st['ratio']}입니다. 동네를 선택하면 건물별 매매·전월세 거래를 볼 수 있습니다."
      seo("#{do_short} #{sg} 빌라·오피스텔 실거래가 - 동네별 매매·전세가율", "#{do_short} #{sg} 연립다세대·오피스텔 #{f(list.size)}개 건물 실거래가. 동네별 중앙 매매가, 평균 전세가율, 거래 많은 건물.")
      faq([["#{sg} 빌라 평균 매매가는 얼마인가요?", "건물별 대표 평형(거래가 가장 많은 전용면적)의 최근 3년 평균 매매가의 중앙값이 #{st['median']}입니다. 면적과 준공연도에 따라 차이가 크니 동네·건물 페이지에서 평형별로 확인하세요."],
           ["#{sg} 전세가율은 어느 정도인가요?", st['ratioN'] >= 3 ? "매매와 전세 거래를 모두 비교할 수 있는 #{f(st['ratioN'])}개 건물의 평균 전세가율은 #{st['ratio']}입니다. 건물마다 차이가 크므로 계약하려는 건물의 수치를 따로 확인하세요." : '비교할 수 있는 건물이 적어 평균 전세가율을 계산하지 못했습니다.']])
    end
  end

  class DongHubPage < VBasePage
    def initialize(site, do_short, sg, dong, list, dong_rows, latest)
      setup(site, "region/#{do_short}/#{sg}/#{dong}", 'dong')
      data['doShort'] = do_short
      data['sigungu'] = sg
      data['dong'] = dong
      data['nTotal'] = f(list.size)
      data['latest'] = latest
      st = VillaGenerator.stat(list)
      data['stat'] = st
      sorted = list.sort_by { |b| [-b['score'], b['name']] }
      data['villaRows'] = sorted.select { |b| b['kind'] == 'v' }.first(VillaGenerator::DONG_ROWS).map { |b| VillaGenerator.row(b) }
      data['offiRows'] = sorted.select { |b| b['kind'] == 'o' }.first(VillaGenerator::DONG_ROWS).map { |b| VillaGenerator.row(b) }
      data['nVilla'] = f(list.count { |b| b['kind'] == 'v' })
      data['nOffi'] = f(list.count { |b| b['kind'] == 'o' })
      data['neighbors'] = dong_rows.reject { |h| h['name'] == dong || h['n'] < 2 }.first(12).map { |h| { 'name' => h['name'], 'n' => f(h['n']) } }
      data['aaptUrl'] = "https://wooaapt.wooahouse.com/region/#{do_short}/#{sg}/#{dong}/"
      data['summary'] = "#{do_short} #{sg} #{dong}에는 빌라(연립·다세대) #{data['nVilla']}곳과 오피스텔 #{data['nOffi']}곳의 거래가 최근 3년 안에 신고됐습니다. 건물별 대표 평형 평균 매매가의 중앙값은 #{st['median']}이고, 매매·전세를 비교할 수 있는 건물의 평균 전세가율은 #{st['ratio']}입니다."
      seo("#{sg} #{dong} 빌라·오피스텔 실거래가 - 매매·전세가율", "#{do_short} #{sg} #{dong} 빌라·오피스텔 #{f(list.size)}개 건물의 최근 매매·전월세 실거래가와 전세가율, 거래 많은 건물 목록.")
      faq([["#{dong} 빌라 시세는 어떻게 보나요?", "이 페이지의 표에서 건물별 대표 평형 평균 매매가와 최근 거래일을 확인하고, 건물 상세 페이지에서 평형별 최저·최고가와 최근 거래 내역을 볼 수 있습니다."],
           ['표에 없는 건물은 왜 그런가요?', '최근 3년 매매 또는 최근 2년 전월세 거래가 신고되지 않은 건물은 나오지 않습니다. 거래가 매우 적은 건물은 상세 페이지 없이 표에만 표시될 수 있습니다.']])
    end
  end

  class JeonsePage < VBasePage
    def initialize(site, do_short, list, latest)
      if do_short
        setup(site, "jeonse/#{do_short}", 'jeonse')
        scope = do_short
      else
        setup(site, 'jeonse', 'jeonse')
        scope = '전국'
      end
      data['scope'] = scope
      data['doShort'] = do_short
      data['latest'] = latest
      data['count'] = f(list.size)
      data['rows'] = list.first(do_short ? 100 : 150).map { |b| VillaGenerator.row(b).merge('ratioA' => b['ratioA']) }
      data['summary'] = "#{scope}에서 같은 전용면적 기준 최근 2년 평균 전세 보증금이 평균 매매가의 70% 이상인 빌라·오피스텔 #{f(list.size)}곳을 전세가율이 높은 순으로 정리했습니다. 전세·매매가 각각 2건 이상 신고된 건물만 포함했고, 거래 건수가 적어 실제와 다를 수 있는 참고 자료입니다."
      seo("#{scope} 전세가율 높은 빌라·오피스텔 - 깡통전세 확인 전 참고", "#{scope} 전세가율 70% 이상 빌라·오피스텔 #{f(list.size)}곳. 같은 전용면적 평균 전세 보증금과 평균 매매가 비교(국토교통부 실거래가 기준).")
    end
  end

  # 사이트맵: 5만 건 한도 때문에 40,000건씩 분할 + 인덱스
  class VillaSitemapGenerator < Generator
    safe true
    priority :lowest
    CHUNK = 40_000

    def generate(site)
      urls = site.pages.reject { |p| p.url.to_s.end_with?('.json', '.xml', '.txt', '.js', '.css') || p.url.to_s == '/404.html' || p.data['sitemap'] == false }.map { |p| p.url }.uniq
      base = site.config['url'].to_s
      chunks = urls.each_slice(CHUNK).to_a
      chunks.each_with_index do |c, idx|
        body = +"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        c.each { |u| body << "  <url><loc>#{base}#{u}</loc></url>\n" }
        body << "</urlset>\n"
        site.pages << raw_page(site, "sitemap-#{idx + 1}.xml", body)
      end
      index = +"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<sitemapindex xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
      chunks.each_index { |idx| index << "  <sitemap><loc>#{base}/sitemap-#{idx + 1}.xml</loc></sitemap>\n" }
      index << "</sitemapindex>\n"
      site.pages << raw_page(site, 'sitemap.xml', index)
      Jekyll.logger.info 'VillaSitemap:', "#{urls.size}개 URL → #{chunks.size}개 사이트맵"
    end

    private

    def raw_page(site, name, content)
      pg = PageWithoutAFile.new(site, site.source, '', name)
      pg.content = content
      pg.data['layout'] = nil
      pg.data['sitemap'] = false
      pg
    end
  end
end
