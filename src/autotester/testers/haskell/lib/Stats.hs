{-# LANGUAGE FlexibleInstances #-}
{-# LANGUAGE TupleSections #-}
{-# LANGUAGE LambdaCase #-}
{-# LANGUAGE ViewPatterns #-}
module Stats (statsReporter, consoleStatsReporter) where

-- a paired down version of the Tasty Stats ingredient that crucially does not depend on git:
-- https://hackage.haskell.org/package/tasty-stats

import Control.Concurrent.STM (atomically, readTVar, TVar, STM, retry)
import Control.Monad ((>=>))
import Data.Char (isSpace, isPrint)
import Data.Foldable (fold)
import Data.IntMap (IntMap)
import Data.List (dropWhileEnd, intersperse)
import Data.Monoid (Endo(..))
import Data.Proxy (Proxy(..))
import Data.Tagged (Tagged(..))
import System.Directory (doesFileExist)
import Test.Tasty
import Test.Tasty.Ingredients
import Test.Tasty.Options
import Test.Tasty.Runners
import qualified Data.IntMap as IntMap

newtype StatsFile = StatsFile FilePath

instance IsOption (Maybe StatsFile) where
  defaultValue = Nothing
  parseValue = Just . Just . StatsFile
  optionName = Tagged "stats"
  optionHelp = Tagged "CSV file to store the collected statistics"

-- | Reporter with support to collect statistics in a file.
statsReporter :: Ingredient
statsReporter = TestReporter optDesc runner
  where optDesc = [ Option (Proxy :: Proxy (Maybe StatsFile)) ]
        runner opts tree = do
          StatsFile file <- lookupOption opts
          pure $ collectStats file $ IntMap.fromList $ zip [0..] $ testsNames opts tree

-- | Console reporter with support to collect statistics in a file.
consoleStatsReporter :: Ingredient
consoleStatsReporter = composeReporters consoleTestReporter statsReporter

zipMap :: IntMap a -> IntMap b -> IntMap (a, b)
zipMap a b = IntMap.mapMaybeWithKey (\k v -> (v,) <$> IntMap.lookup k b) a

waitFinished :: TVar Status -> STM Result
waitFinished = readTVar >=> \case
  Done x -> pure x
  _      -> retry

collectStats :: FilePath -> IntMap TestName -> StatusMap -> IO (Time -> IO Bool)
collectStats file names status = do
  results <- atomically (traverse waitFinished status)
  rows    <- resultRow $ IntMap.toList $ zipMap names results
  exists  <- doesFileExist file
  if exists
    then appendFile file $ formatCSV rows ""
    else writeFile  file $ formatCSV (header : rows) ""
  pure $ const $ pure $ and $ fmap resultSuccessful results


foldEndo :: (Functor f, Foldable f) => f (a -> a) -> (a -> a)
foldEndo = appEndo . fold . fmap Endo

formatCSV :: [[String]] -> ShowS
formatCSV = foldEndo . map ((. ('\n':)) . foldEndo . intersperse (',':) . map field)
  where field s | all isValid s = (s++)
                | otherwise        = ('"':) . escape s . ('"':)
        escape ('"':s) = ("\"\""++) . escape s
        escape (c:s)   = (c:) . escape s
        escape []      = id
        isValid ' '    = True
        isValid ','    = False
        isValid c      = isPrint c && not (isSpace c)

header :: [String]
header = ["idx", "name", "time", "result", "description"]

resultRow :: [(Int, (TestName, Result))] -> IO [[String]]
resultRow results = do
  pure $ flip map results $
    \(show -> idx, (name, Result { resultDescription=dropWhileEnd isSpace -> description
                                 , resultShortDescription=result
                                 , resultTime=show -> time })) ->
    [idx, name, time, result, description]
